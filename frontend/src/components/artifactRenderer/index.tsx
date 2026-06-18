import React, { useState } from 'react';
import { Image, Button, Table, Collapse, Space, Typography, Tag } from 'antd';
import { DownloadOutlined, EyeOutlined, FileOutlined, JsonView } from '@ant-design/icons';
import styles from './artifactRenderer.module.scss';

const { Text, Paragraph } = Typography;
const { Panel } = Collapse;

export interface Artifact {
    type: 'text' | 'image' | 'file' | 'json' | 'table';
    mime_type: string;
    title?: string;
    content?: any;
    preview_url?: string;
    download_url?: string;
    size?: number;
    metadata?: Record<string, any>;
}

interface ArtifactRendererProps {
    artifacts: Artifact[];
}

const formatFileSize = (bytes?: number): string => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const TextArtifact: React.FC<{ artifact: Artifact }> = ({ artifact }) => {
    const content = artifact.content || '';
    const isLong = typeof content === 'string' && content.length > 500;
    const isTruncated = typeof content === 'string' && content.endsWith('... (truncated)');

    return (
        <div className={styles.artifactItem}>
            <div className={styles.artifactHeader}>
                <Tag color="blue">text</Tag>
                <Text strong>{artifact.title || 'Text Content'}</Text>
                {artifact.mime_type && <Text type="secondary" className={styles.mimeType}>{artifact.mime_type}</Text>}
                {isTruncated && <Tag color="warning">Truncated preview</Tag>}
            </div>
            <div className={styles.artifactContent}>
                {isLong ? (
                    <Collapse ghost>
                        <Panel header="Show full content" key="1">
                            <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                                {content}
                            </Paragraph>
                        </Panel>
                    </Collapse>
                ) : (
                    <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                        {content}
                    </Paragraph>
                )}
                {artifact.download_url && (
                    <div className={styles.actionRow}>
                        <Button
                            type="primary"
                            icon={<DownloadOutlined />}
                            onClick={() => window.open(artifact.download_url, '_blank')}
                        >
                            Download Full Content
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
};

const ImageArtifact: React.FC<{ artifact: Artifact }> = ({ artifact }) => {
    const imageUrl = artifact.preview_url || artifact.download_url || (typeof artifact.content === 'string' ? artifact.content : '');

    return (
        <div className={styles.artifactItem}>
            <div className={styles.artifactHeader}>
                <Tag color="green">image</Tag>
                <Text strong>{artifact.title || 'Image'}</Text>
                {artifact.size && <Text type="secondary" className={styles.mimeType}>{formatFileSize(artifact.size)}</Text>}
            </div>
            <div className={styles.artifactContent}>
                {imageUrl ? (
                    <Image
                        src={imageUrl}
                        alt={artifact.title || 'image'}
                        className={styles.imagePreview}
                    />
                ) : (
                    <div className={styles.placeholder}>
                        <EyeOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                        <Text type="secondary">No image preview available</Text>
                    </div>
                )}
                {artifact.download_url && (
                    <div className={styles.actionRow}>
                        <Button
                            type="primary"
                            icon={<DownloadOutlined />}
                            onClick={() => window.open(artifact.download_url, '_blank')}
                        >
                            Download
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
};

const FileArtifact: React.FC<{ artifact: Artifact }> = ({ artifact }) => {
    return (
        <div className={styles.artifactItem}>
            <div className={styles.artifactHeader}>
                <Tag color="orange">file</Tag>
                <Text strong>{artifact.title || 'File'}</Text>
                {artifact.mime_type && <Text type="secondary" className={styles.mimeType}>{artifact.mime_type}</Text>}
            </div>
            <div className={styles.artifactContent}>
                <div className={styles.fileInfo}>
                    <FileOutlined className={styles.fileIcon} />
                    <div className={styles.fileDetails}>
                        <Text strong>{artifact.title || 'File'}</Text>
                        {artifact.size && <Text type="secondary">{formatFileSize(artifact.size)}</Text>}
                    </div>
                </div>
                <Space>
                    {artifact.download_url && (
                        <Button
                            type="primary"
                            icon={<DownloadOutlined />}
                            onClick={() => window.open(artifact.download_url, '_blank')}
                        >
                            Download
                        </Button>
                    )}
                    {artifact.preview_url && (
                        <Button
                            icon={<EyeOutlined />}
                            onClick={() => window.open(artifact.preview_url, '_blank')}
                        >
                            Preview
                        </Button>
                    )}
                </Space>
            </div>
        </div>
    );
};

const JsonArtifact: React.FC<{ artifact: Artifact }> = ({ artifact }) => {
    const [expanded, setExpanded] = useState(false);
    const jsonContent = typeof artifact.content === 'string' ? artifact.content : JSON.stringify(artifact.content, null, 2);
    const isTruncated = typeof jsonContent === 'string' && jsonContent.endsWith('... (truncated)');

    return (
        <div className={styles.artifactItem}>
            <div className={styles.artifactHeader}>
                <Tag color="purple">json</Tag>
                <Text strong>{artifact.title || 'JSON Data'}</Text>
                {isTruncated && <Tag color="warning">Truncated preview</Tag>}
            </div>
            <div className={styles.artifactContent}>
                <Collapse
                    ghost
                    activeKey={expanded ? ['1'] : []}
                    onChange={() => setExpanded(!expanded)}
                >
                    <Panel header={expanded ? 'Collapse JSON' : 'Expand JSON'} key="1">
                        <pre className={styles.jsonCode}>
                            {jsonContent}
                        </pre>
                    </Panel>
                </Collapse>
                {artifact.download_url && (
                    <div className={styles.actionRow}>
                        <Button
                            type="primary"
                            icon={<DownloadOutlined />}
                            onClick={() => window.open(artifact.download_url, '_blank')}
                        >
                            Download Full JSON
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
};

const TableArtifact: React.FC<{ artifact: Artifact }> = ({ artifact }) => {
    const data = artifact.content;
    const columns = data?.columns || [];
    const rows = data?.rows || [];
    const truncated = data?.truncated;
    const isTruncated = truncated && (truncated.total_rows > truncated.shown_rows || truncated.total_columns > truncated.shown_columns);

    const tableColumns = columns.map((col: string, index: number) => ({
        title: col,
        dataIndex: `col_${index}`,
        key: `col_${index}`,
    }));

    const tableData = rows.map((row: any[], index: number) => {
        const rowData: Record<string, any> = { key: `row_${index}` };
        row.forEach((cell, colIndex) => {
            rowData[`col_${colIndex}`] = cell;
        });
        return rowData;
    });

    const truncationNote = isTruncated ? (
        <Tag color="warning">
            Showing {truncated.shown_rows} of {truncated.total_rows} rows
            {truncated.total_columns > truncated.shown_columns && `, ${truncated.shown_columns} of ${truncated.total_columns} cols`}
        </Tag>
    ) : null;

    return (
        <div className={styles.artifactItem}>
            <div className={styles.artifactHeader}>
                <Tag color="cyan">table</Tag>
                <Text strong>{artifact.title || 'Table Data'}</Text>
                {rows.length > 0 && <Text type="secondary" className={styles.mimeType}>
                    {truncated ? `${truncated.total_rows} rows` : `${rows.length} rows`}
                </Text>}
                {truncationNote}
            </div>
            <div className={styles.artifactContent}>
                {columns.length > 0 && rows.length > 0 ? (
                    <Table
                        columns={tableColumns}
                        dataSource={tableData}
                        size="small"
                        pagination={rows.length > 10 ? { pageSize: 10 } : false}
                        scroll={{ x: 'max-content' }}
                    />
                ) : (
                    <div className={styles.placeholder}>
                        <Text type="secondary">No table data available</Text>
                    </div>
                )}
                {artifact.download_url && (
                    <div className={styles.actionRow}>
                        <Button
                            type="primary"
                            icon={<DownloadOutlined />}
                            onClick={() => window.open(artifact.download_url, '_blank')}
                        >
                            Download Full Table
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
};

const ArtifactRenderer: React.FC<ArtifactRendererProps> = ({ artifacts }) => {
    if (!artifacts || artifacts.length === 0) {
        return null;
    }

    const renderArtifact = (artifact: Artifact, index: number) => {
        switch (artifact.type) {
            case 'text':
                return <TextArtifact key={index} artifact={artifact} />;
            case 'image':
                return <ImageArtifact key={index} artifact={artifact} />;
            case 'file':
                return <FileArtifact key={index} artifact={artifact} />;
            case 'json':
                return <JsonArtifact key={index} artifact={artifact} />;
            case 'table':
                return <TableArtifact key={index} artifact={artifact} />;
            default:
                return (
                    <div key={index} className={styles.artifactItem}>
                        <Tag>{artifact.type}</Tag>
                        <Text>{artifact.title || 'Unknown artifact type'}</Text>
                    </div>
                );
        }
    };

    return (
        <div className={styles.artifactList}>
            {artifacts.map((artifact, index) => renderArtifact(artifact, index))}
        </div>
    );
};

export default ArtifactRenderer;
