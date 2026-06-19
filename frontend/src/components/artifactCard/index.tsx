import React, { useMemo } from 'react';
import { Card, Image, Tag, Button, Space, Typography, Table } from 'antd';
import {
  FileOutlined,
  FileTextOutlined,
  TableOutlined,
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
    case 'json':
      return <FileTextOutlined />;
    case 'table':
      return <TableOutlined />;
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
    case 'json':
      return 'orange';
    case 'table':
      return 'purple';
    default:
      return 'default';
  }
};

const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact }) => {
  const { type, mime_type, title, content, preview_url, download_url, size } = artifact;

  const parsedJson = useMemo(() => {
    if (type === 'json' && content) {
      try {
        return JSON.parse(content);
      } catch {
        return null;
      }
    }
    return null;
  }, [type, content]);

  const tableColumns = useMemo(() => {
    if (type === 'table' && content) {
      try {
        const data = JSON.parse(content);
        if (Array.isArray(data) && data.length > 0) {
          const firstRow = data[0];
          return Object.keys(firstRow).map((key) => ({
            title: key,
            dataIndex: key,
            key,
            ellipsis: true,
          }));
        }
      } catch {
        return [];
      }
    }
    return [];
  }, [type, content]);

  const tableData = useMemo(() => {
    if (type === 'table' && content) {
      try {
        const data = JSON.parse(content);
        return Array.isArray(data) ? data.slice(0, 20) : [];
      } catch {
        return [];
      }
    }
    return [];
  }, [type, content]);

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

      case 'json':
        return (
          <pre className={styles.jsonContent}>
            <code>
              {parsedJson ? JSON.stringify(parsedJson, null, 2) : content || ''}
            </code>
          </pre>
        );

      case 'table':
        return (
          <div className={styles.tableContent}>
            <Table
              columns={tableColumns}
              dataSource={tableData}
              size="small"
              pagination={false}
              scroll={{ x: true, y: 200 }}
            />
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
