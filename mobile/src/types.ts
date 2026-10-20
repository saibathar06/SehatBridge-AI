export type Source = { page: number; excerpt: string };
export type Medicine = {
  name: string | null;
  brand_generic: string | null;
  strength: string | null;
  dose: string | null;
  dose_unit: string | null;
  route: string | null;
  frequency: string | null;
  scheduled_times: string[];
  duration: string | null;
  start_date: string | null;
  end_date: string | null;
  food_instructions: string | null;
  special_instructions: string | null;
  source: Source;
  confidence: "high" | "medium" | "low";
  clarification_required: boolean;
  review_flags: string[];
};
export type FollowUp = {
  name: string;
  date: string | null;
  time_window: string | null;
  explicitly_documented: boolean;
  source: Source;
  review_flags: string[];
};
export type Instruction = {
  text: string;
  kind: "diet" | "care";
  direct_instruction: boolean;
  source: Source;
};
export type Extraction = {
  document_type: "prescription" | "discharge" | "laboratory" | "other";
  document_date: string | null;
  institution: string | null;
  clinician: string | null;
  clinical_context: string | null;
  summary: string;
  medicines: Medicine[];
  follow_ups: FollowUp[];
  tests: FollowUp[];
  instructions: Instruction[];
  review_flags: string[];
};
export type ScheduleInput = {
  medicine_index: number;
  times: string[];
  timezone: string;
  start_date: string;
  end_date: string;
  timing_confirmed: boolean;
  clinician_verified: boolean;
  clarification_note: string;
};
export type Profile = {
  id?: string;
  name: string;
  language: "hi" | "en";
  timezone: string;
  chat_history: boolean;
};
export type Treatment = {
  id: string;
  document_id: string;
  revision: number;
  status: "active" | "completed";
  extraction: Extraction;
  confirmed_at: number;
  schedules: (ScheduleInput & { id: string })[];
};
export type MedicalDocument = {
  id: string;
  document_type: string;
  created_at: number;
  status: "queued" | "processing" | "review" | "confirmed" | "error";
  error: string | null;
  pages: { id: string; position: number; mime: string }[];
};
export type Dose = {
  id: string;
  due_at: number;
  status: "upcoming" | "taken" | "skipped" | "missed";
  medicine: Medicine;
  timezone: string;
  treatment_id: string;
};
export type Preferences = {
  enabled: boolean;
  remote_enabled: boolean;
  quiet_start: string | null;
  quiet_end: string | null;
};
export type NotificationIntent = {
  preferences: Preferences;
  doses: { dose_id: string; due_at: number }[];
  max_notifications: number;
  remote_configured: boolean;
};
export type Answer = { answer: string; route: string; sources: Source[] };
