export interface RegionMeta {
  key: string;
  label: string;
  box: [number, number, number, number];
}

export interface InitMeta {
  key: string;
  label: string;
  short_label: string;
  periods: string[];
  note: string;
}

export interface MetaResponse {
  regions: RegionMeta[];
  variables: Record<string, string>;
  initializations: InitMeta[];
  period_labels: Record<string, string>;
}

export interface AnomalyPeriodReading {
  period: string;
  period_label: string;
  prate_mm_day: number | null;
  prate_total: number | null;
  prate_total_unit: string | null;
  tmpsfc_anomaly_k: number | null;
}

export interface AnomalySeriesResponse {
  init: string;
  region: string;
  variable: string;
  readings: AnomalyPeriodReading[];
}

export interface AnomalyTableRow {
  region: string;
  region_label: string;
  period: string;
  period_label: string;
  prate_mm_day: number | null;
  prate_total: number | null;
  prate_total_unit: string | null;
  tmpsfc_anomaly_k: number | null;
}

export interface GridResponse {
  lats: number[];
  lons: number[];
  values: (number | null)[][];
  unit: string;
}

export interface OverlayInfo {
  available: boolean;
  url?: string;
  bounds?: [[number, number], [number, number]];
  vmin?: number;
  vmax?: number;
  unit?: string;
}

export interface EvidenceRow {
  source_system: string;
  evidence_type: string;
  evidence_group: string;
  period: string;
  period_label: string;
  domain: string;
  diagnostic: string;
  value: number | null;
  units: string | null;
  classification: string | null;
  raw_score: number | null;
  weight: number | null;
  weighted_score: number | null;
  support_direction: string | null;
  evidence_strength: string | null;
  confidence: string | null;
  interpretation: string | null;
  limitation: string | null;
}

export interface EvidenceSummaryRow {
  period: string;
  period_label: string;
  period_order: number;
  total_evidence_rows: number | null;
  dry_support_count: number;
  wet_or_rain_support_count: number;
  neutral_or_context_count: number;
  raw_score_sum: number | null;
  weighted_score_sum: number;
  nmme_weighted_score: number;
  cfsv2_weighted_score: number;
  overall_category: string;
  summary_message: string | null;
}

export interface SstProxyRow {
  period: string;
  nino34_anomaly: number;
  iod_west_anomaly: number;
  iod_east_anomaly: number;
  dmi_proxy: number;
  units: string;
  nino34_classification: string;
  dmi_classification: string;
}

export interface TejRow {
  diagnostic: string;
  period: string;
  value: number;
  units: string;
  interpretation: string;
}

export interface DomainRow {
  diagnostic: string;
  period: string;
  domain: string;
  value: number;
  units: string;
  interpretation: string;
}

export interface Cfsv2Row {
  period: string;
  domain: string;
  diagnostic: string;
  value: number;
  units: string;
  classification: string;
  description: string;
}

export interface GalleryImage {
  key: string;
  url: string;
  caption: string;
  group: string;
}

export interface WeightRow {
  evidence_type: string;
  weight: number;
  rationale: string;
}

export interface DomainBox {
  name: string;
  box: [number, number, number, number];
}
