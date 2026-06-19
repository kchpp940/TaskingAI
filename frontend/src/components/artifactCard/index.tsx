import React from 'react';
import { Card, Image, Tag, Button, Space, Typography } from 'antd';
import {
  FileOutlined,
  LinkOutlined,
  CodeOutlined,
  SoundOutlined,
  VideoCameraOutlined,
  DownloadOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { Artifact } from '@/types/artifact';
import styles from './artifactCard.module.scss';

const { Text, Paragraph } = Typography;

interface ArtifactCardProps {
  artifact: Artifact;
}

const formatSize = (bytes?: number): string => {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const getTypeIcon = (type: string) => {
  switch (type) {
    case 'image':
      return <EyeOutlined />;
    case 'file':
      return <FileOutlined />;
    case 'link':
      return <LinkOutlined />;
    case 'code':
      return <CodeOutlined />;
    case 'audio':
      return <SoundOutlined />;
    case 'video':
      return <VideoCameraOutlined />;
    default:
      return <FileOutlined />;
  }
};

const getTypeColor = (type: string): string => {
  switch (type) {
    case 'image':
      return 'green';
    case 'file':
      return 'blue';
    case 'link':
      return 'purple';
    case 'code':
      return 'orange';
    case 'audio':
      return 'cyan';
    case 'video':
      return 'magenta';
    default:
      return 'default';
  }
};

const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact }) => {
  const { type, mime_type, title, content, preview_url, download_url, size } = artifact;

  const renderContent = () => {
    switch (type) {
      case 'image':
        return (
          <div className={styles.imageContainer}>
            {preview_url && (
              <Image
                src={preview_url}
                alt={title || 'image'}
                className={styles.image}
                preview={{ src: download_url || preview_url }}
              />
            )}
          </div>
        );

      case 'text':
        return (
          <Paragraph className={styles.textContent} ellipsis={{ rows: 4 }}>
            {content || ''}
          </Paragraph>
        );

      case 'code':
        return (
          <pre className={styles.codeContent}>
            <code>{content || ''}</code>
          </pre>
        );

      case 'link':
        return (
          <div className={styles.linkContent}>
            <LinkOutlined className={styles.linkIcon} />
            <Text type="secondary" ellipsis>
              {download_url || ''}
            </Text>
          </div>
        );

      case 'audio':
        return (
          <div className={styles.audioContent}>
            {download_url && <audio src={download_url} controls className={styles.audio} />}
          </div>
        );

      case 'video':
        return (
          <div className={styles.videoContent}>
            {download_url && (
              <video src={download_url} controls className={styles.video}>
                Your browser does not support the video tag.
              </video>
            )}
          </div>
        );

      case 'file':
      default:
        return (
          <div className={styles.fileContent}>
            <FileOutlined className={styles.fileIcon} />
            <div className={styles.fileInfo}>
              <Text strong ellipsis>
                {title || 'File'}
              </Text>
              <Text type="secondary" className={styles.mimeType}>
                {mime_type}
              </Text>
            </div>
          </div>
        );
    }
  };

  return (
    <Card
      className={styles.artifactCard}
      size="small"
      title={
        <Space>
          <Tag color={getTypeColor(type)} icon={getTypeIcon(type)}>
            {type}
          </Tag>
          <Text strong ellipsis className={styles.title}>
            {title || mime_type}
          </Text>
        </Space>
      }
      extra={
        <Space>
          {size && <Text type="secondary">{formatSize(size)}</Text>}
          {download_url && (
            <Button
              type="text"
              icon={<DownloadOutlined />}
              size="small"
              onClick={() => window.open(download_url, '_blank')}
            >
              Download
            </Button>
          )}
        </Space>
      }
    >
      {renderContent()}
    </Card>
  );
};

export default ArtifactCard;
