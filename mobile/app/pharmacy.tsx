import React, { useState } from "react";
import { Text, View } from "react-native";
import { useLoad, message } from "../src/hooks";
import { post } from "../src/api";
import { Screen, Card, Button, Notice, Field, styles } from "../src/ui";
type Inventory = {
  id: string;
  provider_id: string;
  name: string;
  price_paise: number;
};
type Order = {
  id: string;
  total_paise: number;
  status: string;
  items: { name: string; quantity: number }[];
};
export default function Pharmacy() {
  const providers = useLoad<{ id: string; name: string; address: string }[]>(
    "/demo/providers?kind=pharmacy",
  );
  const inventory = useLoad<Inventory[]>("/demo/inventory");
  const orders = useLoad<Order[]>("/demo/orders");
  const [search, setSearch] = useState("");
  const [cart, setCart] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const total = (inventory.data || []).reduce(
    (sum, i) => sum + i.price_paise * (cart[i.id] || 0),
    0,
  );
  async function place() {
    setBusy(true);
    setError("");
    try {
      await post("/demo/orders", {
        items: Object.entries(cart)
          .filter(([, q]) => q > 0)
          .map(([inventory_id, quantity]) => ({ inventory_id, quantity })),
      });
      setCart({});
      setInfo(
        "Demonstration order saved — no real pharmacy has received this order.",
      );
      await orders.reload();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      back
      title="Pharmacy demonstration."
      subtitle="Explore a simulated cart and order history."
    >
      <Notice>
        Demonstration order — no real pharmacy will receive this order. All
        inventory, prices and locations are synthetic. These are not substitutes
        for prescribed medicines.
      </Notice>
      {providers.data?.map((p) => (
        <Card key={p.id}>
          <Text style={styles.h3}>{p.name}</Text>
          <Text style={styles.muted}>{p.address}</Text>
        </Card>
      ))}
      <Field
        label="Search synthetic medicine inventory"
        value={search}
        onChangeText={setSearch}
      />
      {!!(error || inventory.error || orders.error) && (
        <Notice error>{error || inventory.error || orders.error}</Notice>
      )}
      {!!info && <Notice>{info}</Notice>}
      {inventory.data
        ?.filter((i) => i.name.toLowerCase().includes(search.toLowerCase()))
        .map((i) => (
          <Card key={i.id}>
            <Text style={styles.h3}>{i.name}</Text>
            <Text style={styles.muted}>
              ₹{(i.price_paise / 100).toFixed(2)} · synthetic price
            </Text>
            <View style={styles.between}>
              <Button
                title="Remove one"
                tone="soft"
                disabled={!cart[i.id]}
                onPress={() =>
                  setCart({
                    ...cart,
                    [i.id]: Math.max(0, (cart[i.id] || 0) - 1),
                  })
                }
              />
              <Text style={styles.h3}>{cart[i.id] || 0}</Text>
              <Button
                title="Add one"
                tone="soft"
                disabled={(cart[i.id] || 0) >= 10}
                onPress={() =>
                  setCart({ ...cart, [i.id]: (cart[i.id] || 0) + 1 })
                }
              />
            </View>
          </Card>
        ))}
      <Button
        title={`Place simulated order · ₹${(total / 100).toFixed(2)}`}
        disabled={!total}
        loading={busy}
        onPress={() => void place()}
      />
      <Text style={styles.h2}>Demonstration order history</Text>
      {orders.data?.map((o) => (
        <Card key={o.id}>
          <Text style={styles.h3}>
            ₹{(o.total_paise / 100).toFixed(2)} · {o.status}
          </Text>
          {o.items.map((i, n) => (
            <Text key={n} style={styles.muted}>
              {i.name} × {i.quantity}
            </Text>
          ))}
          <Text style={styles.muted}>
            Demonstration order — no real pharmacy has received this order.
          </Text>
        </Card>
      ))}
    </Screen>
  );
}
