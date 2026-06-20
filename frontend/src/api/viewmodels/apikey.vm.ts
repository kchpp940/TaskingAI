export interface ApikeyDto {
  object: string;
  apikey_id: string;
  name: string;
  apikey: string;
  created_timestamp: number;
  updated_timestamp: number;
}

export interface ApikeyVM {
  id: string;
  key: string;
  apikeyId: string;
  name: string;
  apikey: string;
  maskedApikey: string;
  createdAt: string;
  updatedAt: string;
  createdTimestamp: number;
  updatedTimestamp: number;
}

export interface ApikeyCreateRequest {
  name: string;
}

export interface ApikeyUpdateRequest {
  name?: string;
}
