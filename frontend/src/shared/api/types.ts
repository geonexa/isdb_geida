export type User = {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  is_staff: boolean;
  is_reviewer: boolean;
  is_analyst: boolean;
};

export type VerifyState = {
  masked_email: string;
  resend_wait: number;
  minutes: number;
  dev_code: string | null;
};

export type Module = {
  slug: string;
  name: string;
  icon: string;
  summary: string;
  features: string[];
  url?: string;
  /** Only shown to users with one of these roles (e.g. "analyst"). */
  roles?: string[];
};

export type CycleStage = {
  key: string;
  stage: string;
  instrument: string;
  question: string;
  phase: string;
  image: string;
  alt: string;
  outputs: string[];
  value: string;
};

export type Component = {
  key: string;
  name: string;
  title: string;
  image: string;
  text: string;
  items: string[];
};

export type SiteContent = {
  primary: Module[];
  hub: Module[];
  cycle: CycleStage[];
  components: Component[];
};
