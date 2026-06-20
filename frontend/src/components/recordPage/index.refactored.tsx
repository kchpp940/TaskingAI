import { useState, useEffect } from 'react'
import { Spin, Tag, Tooltip, Space, Modal, Button, Input, Radio, Form, Upload, message } from 'antd'
import { InboxOutlined, PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import styles from './recordPage.module.scss'
import { toast } from 'react-toastify'
import {
  recordService,
  collectionService,
  handleApiError,
  RecordVM,
  RecordType,
  RecordStatus,
  RecordUpdateRequest,
} from '@/api'

interface RecordPageRefactoredProps {
  collectionId: string
}

function RecordPageRefactored({ collectionId }: RecordPageRefactoredProps) {
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState<RecordVM[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [currentRecord, setCurrentRecord] = useState<RecordVM | null>(null)
  const [form] = Form.useForm()

  useEffect(() => {
    if (collectionId) {
      fetchRecords()
    }
  }, [collectionId])

  const fetchRecords = async () => {
    setLoading(true)
    try {
      const result = await recordService.list(collectionId, { limit: 20 })
      setRecords(result.data)
      setHasMore(result.has_more)
    } catch (error) {
      handleApiError(error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      const params: any = {
        type: values.type,
        title: values.title || undefined,
      }

      if (values.type === RecordType.TEXT) {
        params.content = { text: values.textContent }
      } else if (values.type === RecordType.WEB) {
        params.content = { url: values.url }
      } else if (values.type === RecordType.FILE) {
        params.file_id = values.fileId
      }

      await recordService.create(collectionId, params)
      setCreateModalOpen(false)
      form.resetFields()
      fetchRecords()
      toast.success('Record created successfully')
    } catch (error) {
      handleApiError(error)
    }
  }

  const handleEdit = async (values: any) => {
    if (!currentRecord) return
    try {
      const params: RecordUpdateRequest = {}

      if (values.title !== currentRecord.title) {
        params.title = values.title || undefined
      }

      if (currentRecord.type === RecordType.TEXT && values.textContent !== currentRecord.textContent) {
        params.content = { text: values.textContent }
      }

      if (Object.keys(params).length > 0) {
        await recordService.update(collectionId, currentRecord.recordId, params)
      }

      setEditModalOpen(false)
      setCurrentRecord(null)
      form.resetFields()
      fetchRecords()
      toast.success('Record updated successfully')
    } catch (error) {
      handleApiError(error)
    }
  }

  const handleDelete = async () => {
    if (!currentRecord) return
    try {
      await recordService.delete(collectionId, currentRecord.recordId)
      setDeleteModalOpen(false)
      setCurrentRecord(null)
      fetchRecords()
      toast.success('Record deleted successfully')
    } catch (error) {
      handleApiError(error)
    }
  }

  const openEditModal = (record: RecordVM) => {
    setCurrentRecord(record)
    form.setFieldsValue({
      title: record.title,
      type: record.type,
      textContent: record.textContent,
    })
    setEditModalOpen(true)
  }

  const openDeleteModal = (record: RecordVM) => {
    setCurrentRecord(record)
    setDeleteModalOpen(true)
  }

  const renderRecordContent = (record: RecordVM) => {
    if (record.type === RecordType.TEXT) {
      return (
        <Tooltip title={record.textContent}>
          <div className={styles.textContent}>
            {record.displayContent}
          </div>
        </Tooltip>
      )
    }

    if (record.type === RecordType.FILE) {
      return (
        <div className={styles.fileContent}>
          <Tag>{record.fileContent?.fileType || 'FILE'}</Tag>
          <span>{record.fileContent?.fileName || record.displayContent}</span>
        </div>
      )
    }

    if (record.type === RecordType.WEB) {
      return (
        <div className={styles.webContent}>
          <a href={record.webContent?.url} target="_blank" rel="noreferrer">
            {record.webContent?.url || record.displayContent}
          </a>
        </div>
      )
    }

    return <span>{record.displayContent}</span>
  }

  return (
    <div className={styles.recordPage}>
      <div className={styles.header}>
        <h2>Records</h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalOpen(true)}
        >
          Create Record
        </Button>
      </div>

      <Spin spinning={loading}>
        <div className={styles.recordList}>
          {records.length === 0 && !loading ? (
            <div className={styles.emptyState}>
              <InboxOutlined className={styles.emptyIcon} />
              <p>No records yet. Create one to get started.</p>
            </div>
          ) : (
            records.map((record) => (
              <div key={record.key} className={styles.recordItem}>
                <div className={styles.recordMain}>
                  <div className={styles.recordHeader}>
                    <Tag color="blue">{record.typeLabel}</Tag>
                    <span className={styles.recordTitle}>{record.displayTitle}</span>
                    <Tag className={`${styles.statusTag} ${record.statusClass}`}>
                      {record.statusLabel}
                    </Tag>
                  </div>
                  <div className={styles.recordContent}>
                    {renderRecordContent(record)}
                  </div>
                  <div className={styles.recordMeta}>
                    <span>Created: {record.createdTime}</span>
                    {record.updatedTime && record.updatedTime !== record.createdTime && (
                      <span>Updated: {record.updatedTime}</span>
                    )}
                  </div>
                </div>
                <div className={styles.recordActions}>
                  <Tooltip title="Edit">
                    <EditOutlined onClick={() => openEditModal(record)} />
                  </Tooltip>
                  <Tooltip title="Delete">
                    <DeleteOutlined onClick={() => openDeleteModal(record)} />
                  </Tooltip>
                </div>
              </div>
            ))
          )}
        </div>
      </Spin>

      <Modal
        title="Create Record"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false)
          form.resetFields()
        }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item label="Type" name="type" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value={RecordType.TEXT}>Text</Radio>
              <Radio value={RecordType.WEB}>Web URL</Radio>
              <Radio value={RecordType.FILE}>File</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item label="Title (optional)" name="title">
            <Input placeholder="Give this record a title" />
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.type !== curr.type}>
            {({ getFieldValue }) => {
              const type = getFieldValue('type')
              if (type === RecordType.TEXT) {
                return (
                  <Form.Item
                    label="Content"
                    name="textContent"
                    rules={[{ required: true, message: 'Please enter text content' }]}
                  >
                    <Input.TextArea rows={6} placeholder="Enter text content..." />
                  </Form.Item>
                )
              }
              if (type === RecordType.WEB) {
                return (
                  <Form.Item
                    label="URL"
                    name="url"
                    rules={[
                      { required: true, message: 'Please enter a URL' },
                      { type: 'url', message: 'Please enter a valid URL' },
                    ]}
                  >
                    <Input placeholder="https://example.com" />
                  </Form.Item>
                )
              }
              if (type === RecordType.FILE) {
                return (
                  <Form.Item
                    label="File"
                    name="fileId"
                    rules={[{ required: true, message: 'Please upload a file' }]}
                  >
                    <Upload.Dragger
                      beforeUpload={async (file) => {
                        try {
                          const formData = new FormData()
                          formData.append('file', file)
                          const result = await recordService.uploadFile(formData)
                          form.setFieldsValue({ fileId: result.file_id })
                          message.success('File uploaded successfully')
                        } catch (e) {
                          handleApiError(e)
                        }
                        return false
                      }}
                    >
                      <p className="ant-upload-drag-icon">
                        <InboxOutlined />
                      </p>
                      <p className="ant-upload-text">Click or drag file to this area to upload</p>
                    </Upload.Dragger>
                  </Form.Item>
                )
              }
              return null
            }}
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Edit Record"
        open={editModalOpen}
        onCancel={() => {
          setEditModalOpen(false)
          setCurrentRecord(null)
          form.resetFields()
        }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleEdit}>
          <Form.Item label="Title (optional)" name="title">
            <Input placeholder="Give this record a title" />
          </Form.Item>

          <Form.Item noStyle shouldUpdate={() => true}>
            {({ getFieldValue }) => {
              const type = getFieldValue('type')
              if (type === RecordType.TEXT) {
                return (
                  <Form.Item
                    label="Content"
                    name="textContent"
                    rules={[{ required: true, message: 'Please enter text content' }]}
                  >
                    <Input.TextArea rows={6} placeholder="Enter text content..." />
                  </Form.Item>
                )
              }
              return null
            }}
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Delete Record"
        open={deleteModalOpen}
        onCancel={() => {
          setDeleteModalOpen(false)
          setCurrentRecord(null)
        }}
        onOk={handleDelete}
        okButtonProps={{ danger: true }}
      >
        <p>Are you sure you want to delete "{currentRecord?.displayTitle}"?</p>
        <p>This action cannot be undone.</p>
      </Modal>
    </div>
  )
}

export default RecordPageRefactored
