export type ArtifactType = 'text' | 'image' | 'file' | 'link' | 'code' | 'audio' | 'video';

export interface Artifact {
  type: ArtifactType;
  mime_type: string;
  title?: string;
  content?: string;
  preview_url?: string;
  download_url?: string;
  size?: number;
  metadata?: Record<string, any>;
}

export interface MessageContent {
  text: string;
  artifacts?: Artifact[];
}

export interface Message {
  object: string;
  assistant_id: string;
  chat_id: string;
  message_id: string;
  role: 'user' | 'assistant';
  content: MessageContent;
  num_tokens: number;
  metadata: Record<string, any>;
  created_timestamp: number;
  updated_timestamp: number;
}
