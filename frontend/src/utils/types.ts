export interface ArticleMeta {
  title: string;
  link: string;
  source: string;
  date: string;
  tags: string[];
}

export interface DailyEntry {
  type: "daily";
  date: string;
  generated_at: string;
  article_count: number;
  sources: string[];
  summary: string;
  articles: ArticleMeta[];
}

export interface WeeklyEntry {
  type: "weekly";
  week_label: string;
  generated_at: string;
  daily_dates: string[];
  summary: string;
}

export interface MonthlyEntry {
  type: "monthly";
  month_label: string;
  generated_at: string;
  weekly_labels: string[];
  summary: string;
}

export type DigestEntry = DailyEntry | WeeklyEntry | MonthlyEntry;

export interface IndexItem {
  file: string;
  label: string;
  date: string;
  article_count?: number;
}

export interface DataIndex {
  daily: IndexItem[];
  weekly: IndexItem[];
  monthly: IndexItem[];
  last_updated: string;
}
