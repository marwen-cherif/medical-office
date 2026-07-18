import type { components } from './schema';

type S = components['schemas'];

// --- Paramétrage (existant) --------------------------------------------------
export type Template = S['TemplateOut'];
export type Placeholders = S['PlaceholdersOut'];
export type Field = S['FieldOut'];
export type Category = S['CategoryOut'];
export type CategoryImport = S['CategoryImportOut'];
export type CategoryExport = S['CategoryExportOut'];
export type CategoryUpsertIn = S['CategoryUpsertIn'];
export type MailTemplate = S['MailTemplateOut'];
export type MailTemplateIn = S['MailTemplateIn'];
export type Printers = S['PrintersOut'];
export type PrintConfig = S['PrintConfigOut'];
export type Acte = S['ActeOut'];
export type ActeIn = S['ActeIn'];
export type ActeList = S['ActeListOut'];
export type ActeImport = S['ActeImportOut'];
export type ActeExport = S['ActeExportOut'];
export type WhatsAppSettings = S['WhatsAppSettingsOut'];
export type WhatsAppSettingsIn = S['WhatsAppSettingsIn'];
export type FeaturesSettings = S['FeaturesSettingsOut'];
export type FeaturesSettingsIn = S['FeaturesSettingsIn'];

// --- Patients ----------------------------------------------------------------
export interface PatientPhone {
  id?: number | null;
  patient_id?: number;
  telephone: string;
  relation: string;
  is_whatsapp: boolean;
}

export type Patient = Omit<S['PatientOut'], 'telephones'> & {
  telephones?: PatientPhone[];
};

export type PatientIn = Omit<S['PatientIn'], 'telephones'> & {
  telephones: PatientPhone[];
};

export type PatientList = S['PatientListOut'];
export type PatientDetail = S['PatientDetailOut'];
export type Solde = S['SoldeOut'];

// --- Clinique (plans, actes, paiements, encaissements) -----------------------
export type Prestation = S['PrestationOut'];
export type PrestationIn = S['PrestationIn'];
export type Plan = S['PlanOut'];
export type PlanIn = S['PlanIn'];
export type PlanGroup = S['PlanGroupOut'];
export type Totaux = S['TotauxOut'];
export type Clinical = S['ClinicalOut'];
export type Paiement = S['PaiementOut'];
export type PaiementIn = S['PaiementIn'];
export type Encaissement = S['EncaissementOut'];
export type Encaissements = S['EncaissementsOut'];
export type Creance = S['CreanceOut'];
export type AuditEntry = S['AuditOut'];
export type ReglementIn = S['ReglementIn'];
export type CascadeIn = S['CascadeIn'];
export type CascadeOut = S['CascadeOut'];

// --- Documents & génération --------------------------------------------------
export type DocumentT = S['DocumentOut'];
export type DocumentList = S['DocumentListOut'];
export type DocumentRow = S['DocumentRow'];
export type DocumentRows = S['DocumentRowsOut'];
export type GenForm = S['GenFormOut'];
export type GenField = S['GenFieldOut'];
export type GenActesSource = S['GenActesSource'];
export type GenActeLine = S['GenActeLine'];
export type GenTemplate = S['GenTemplateOut'];
export type DraftIn = S['DraftIn'];
export type GenerateIn = S['GenerateIn'];
export type NewActeIn = S['NewActeIn'];
export type SendIn = S['SendIn'];

// --- Finances ----------------------------------------------------------------
export type FinanceRow = S['FinanceRow'];
export type Paiements = S['PaiementsOut'];
export type Depenses = S['DepensesOut'];
export type DepenseRow = S['DepenseRow'];

// --- Prestataires ------------------------------------------------------------
export type Prestataire = S['PrestataireOut'];
export type PrestataireIn = S['PrestataireIn'];
export type PrestataireList = S['PrestataireListOut'];
export type PrestataireDetail = S['PrestataireDetailOut'];
export type Facture = S['FactureOut'];
export type Depense = S['DepenseOut'];
export type DepenseIn = S['DepenseIn'];
export type ReglementDepenseIn = S['ReglementDepenseIn'];

export type PrestataireReglement = S['PrestataireReglementOut'];
export type PrestataireReglements = S['PrestataireReglementListOut'];
export type DepenseReglement = S['DepenseReglementOut'];

// --- Travaux (jobs) ----------------------------------------------------------
export type Job = S['JobOut'];
export type JobItem = S['JobItemOut'];
export type JobList = S['JobListOut'];
export type JobDetail = S['JobDetailOut'];

// --- Tableau de bord ---------------------------------------------------------
export type Dashboard = S['DashboardOut'];
export type Kpis = S['KpisOut'];
export type DocTypeCount = S['DocTypeCount'];

// --- Rappels -----------------------------------------------------------------
// Types définis manuellement (schéma non encore régénéré).
export type RappelType = 'alerte_interne' | 'message_patient';
export type RappelEtat = 'planifie' | 'du' | 'a_envoyer' | 'envoye' | 'traite' | 'annule';

export interface Rappel {
  id: number;
  type: RappelType;
  titre: string;
  echeance: string;
  etat: RappelEtat;
  lu: boolean;
  patient_id?: number | null;
  document_id?: number | null;
  message?: string | null;
  created_at?: string | null;
  notified_at?: string | null;
  sent_at?: string | null;
  /** "NOM Prénom" si rattaché à un patient (fourni par la liste). */
  patient_display?: string | null;
}

export interface RappelIn {
  type: RappelType;
  titre: string;
  echeance: string;
  patient_id?: number | null;
  document_id?: number | null;
  message?: string | null;
}

export interface RappelList {
  items: Rappel[];
  total: number;
}

export interface RappelCountActifs {
  count: number;
}

export interface RappelProcessDus {
  processed: number;
}

export interface WhatsAppLinkOut {
  url: string;
  phone_id?: number | null;
}

export interface RappelsSettingsOut {
  notifs_enabled: boolean;
  scheduler_interval: number;
  default_country: string;
  task_present: boolean;
  task_enabled: boolean;
  task_status?: string | null;
  task_last_run?: string | null;
  task_next_run?: string | null;
}

export interface RappelsSettingsIn {
  notifs_enabled: boolean;
  scheduler_interval: number;
  default_country: string;
}
