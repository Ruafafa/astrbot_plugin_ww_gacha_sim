
export type Rarity = '5star' | '4star' | '3star';
export type Language = 'zh' | 'en';

export interface GachaItem {
  id: number;
  name: string;
  rarity: Rarity;
  type: string;
  affiliated_type: string;
  config_group: string;
  portrait_path: string;
}

export interface SoftPityInterval {
  start_pull: number;
  end_pull: number;
  increment: number;
}

export interface ProbabilityProgression {
  hard_pity_pull: number;
  hard_pity_rate: number;
  soft_pity: SoftPityInterval[];
}

export interface PoolConfig {
  filename?: string;
  name: string;
  description?: string;
  config_group: string;
  probability_settings: {
    base_5star_rate: number;
    base_4star_rate: number;
    base_3star_rate: number;
    up_5star_rate: number;
    up_4star_rate: number;
    four_star_character_rate: number;
  };
  rate_up_item_ids: {
    '5star': number[];
    '4star': number[];
  };
  included_item_ids: {
    '5star': number[];
    '4star': number[];
    '3star': number[];
  };
  probability_progression: {
    '5star': ProbabilityProgression;
    '4star': ProbabilityProgression;
  };
}

export type ViewType = 'configs' | 'items' | 'editor';
