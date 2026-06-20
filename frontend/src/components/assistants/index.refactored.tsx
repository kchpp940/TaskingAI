import styles from './assistants.module.scss'
import { fetchModelsData, fetchRetrievalData, fetchActionData } from '../../Redux/actions.ts'
import { useDispatch, useSelector } from 'react-redux';
import { PlusOutlined } from '@ant-design/icons';
import { useEffect, useState, useRef } from 'react'
import ModelModal from '../modelModal/index'
import { fetchPluginData } from '../../Redux/actions';
import ModalTable from '../modalTable/index'
import tooltipTitle from '../../contents/tooltipTitle.tsx'
import { fetchAssistantsData } from '@/Redux/actions.ts'
import CreateCollection from '../createCollection/index.tsx';
import { setPlaygroundSelect, setPlaygroundAssistantId } from '@/Redux/actions/playground.ts'
import EditIcon from '../../assets/img/editIcon.svg?react'
import ViewCode from '@/commonComponent/viewCode/index.tsx'
import MoreIcon from '@/assets/img/moreIcon.svg?react'
import JumpIcon from '../../assets/img/assistantJumpIcon.svg?react'
import { toast } from 'react-toastify'
import DeleteModal from '../deleteModal/index.tsx'
import DrawerAssistant from '../drawerAssistant/index'
import closeIcon from '../../assets/img/x-close.svg'
import { useNavigate } from 'react-router-dom';
import { ChildRefType } from '../../constant/index.ts'
import ActionDrawer from '../actionDrawer/index.tsx';
import ModalFooterEnd from '../modalFooterEnd/index'
import { useTranslation } from "react-i18next";
import CreatePlugin from '../createPlugin/index.tsx';
import { valueLimit } from '@/constant/assistant.ts'
import CommonComponents from '../../contents/index'
import {
  Button,
  Space, Drawer, Spin, Modal, Tooltip, Popover
} from 'antd';

import {
  assistantService,
  modelService,
  actionService,
  collectionService,
  pluginService,
  authService,
  handleApiError,
  AssistantVM,
  ModelVM,
  ActionVM,
  RetrievalRefVM,
  ToolRefVM,
  AssistantCreateRequest,
  AssistantUpdateRequest,
  ActionBulkCreateRequest,
  commonDataType,
} from '@/api';

function AssistantRefactored() {
  const dispatch = useDispatch();
  const { pluginLists } = useSelector((state: any) => state.plugin);
  const { retrievalLists } = useSelector((state: any) => state.retrieval);
  const { users, loading } = useSelector((state: any) => state.user);
  const { assistantTableColumn, modelsTableColumn } = CommonComponents();
  const { assistantPlaygroundId } = useSelector((state: any) => state.assistantId)
  const { tooltipEditTitle, tooltipPlaygroundTitle, tooltipMoreTitle } = tooltipTitle();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [bundilesList, setBundlesList] = useState<any[]>([])
  const [isVisible, setIsVisible] = useState(true);
  const [record, setRecord] = useState<AssistantVM | null>(null)
  const [originalModelData, setOriginalModelData] = useState<any>()

  const columns = [...assistantTableColumn]
  columns.push({
    title: `${t('projectColumnActions')}`,
    key: 'action',
    width: 157,
    fixed: 'right',
    render: (_action: string, record: AssistantVM) => (
      <Space size="middle">
        <div onClick={() => handleJump(record)} className='table-edit-icon'>
          <Tooltip placement='bottom' title={tooltipPlaygroundTitle} color='#fff' arrow={false} overlayClassName='table-tooltip'>
            <JumpIcon />
          </Tooltip>
        </div>
        <div onClick={() => handleEdit(record)} className='table-edit-icon'>
          <Tooltip placement='bottom' title={tooltipEditTitle} color='#fff' arrow={false} overlayClassName='table-tooltip'>
            <EditIcon />
          </Tooltip>
        </div>
        <div className='table-edit-icon' onClick={() => setRecord(record)}>
          {isVisible ? <Tooltip placement='bottom' title={tooltipMoreTitle} color='#fff' arrow={false} overlayClassName='table-tooltip'>
            <Popover trigger="click" placement='bottom' content={content} arrow={false}>
              <MoreIcon />
            </Popover>
          </Tooltip> : <MoreIcon />}
        </div>
      </Space>
    ),
  });

  const [assistantsList, setAssistantsList] = useState<AssistantVM[]>([])
  const drawerAssistantRef = useRef<any>(null);
  const [OpenDrawer, setOpenDrawer] = useState(false)
  const [Authentication, setAuthentication] = useState('')
  const [radioValue, setRadioValue] = useState('none')
  const [selectedRetrievalRows, setSelectedRetrievalRows] = useState<RetrievalRefVM[]>([])
  const [options, setOptions] = useState<ModelVM[]>([])
  const [limit, setLimit] = useState(20)
  const [modelLimit, setModelLimit] = useState(20)
  const [updatePrevButton, setUpdatePrevButton] = useState(false)
  const [updateModelPrevButton, setUpdateModelPrevButton] = useState(false)
  const [selectedActionsRows, setSelectedActionsRows] = useState<ToolRefVM[]>([])
  const [OpenDeleteModal, setOpenDeleteModal] = useState(false)
  const [drawerTitle, setDrawerTitle] = useState('Create Assistant')
  const [drawerName, setDrawerName] = useState<string>('')
  const [hasActionMore, setHasActionMore] = useState(false)
  const [tipSchema, setTipSchema] = useState(false)
  const [deleteValue, setDeleteValue] = useState('')
  const [drawerDesc, setDrawerDesc] = useState('')
  const [modalTableOpen, setModalTableOpen] = useState(false)
  const [memoryValue, setMemoryValue] = useState('zero')
  const [retrievalConfig, setRetrievalConfig] = useState('user_message')
  const [OpenActionDrawer, setOpenActionDrawer] = useState(false)
  const [actionList, setActionList] = useState<ActionVM[]>([])
  const [editLoading, setLoading] = useState(false)
  const childRef = useRef<ChildRefType | null>(null);
  const [hasModelMore, setHasModelMore] = useState(false)
  const [custom, setCustom] = useState('')
  const [assistantId, setAssistantId] = useState('')
  const [retrievalList, setRetrievalList] = useState<any[]>([])
  const [schema, setSchema] = useState('')
  const [assistantHasMore, setAssistantHasMore] = useState(false)
  const [modelOne, setModelOne] = useState(false);
  const [systemPromptTemplate, setSystemPromptTemplate] = useState<string[]>(['']);
  const [inputValueOne, setInputValueOne] = useState(20)
  const [openCollectionDrawer, setOpenCollectionDrawer] = useState(false)
  const [inputValueTwo, setInputValueTwo] = useState(2000)
  const [pluginModalOpen, setPluginModalOpen] = useState(false)
  const [selectedPluginGroup, setSelectedPluginGroup] = useState<any[]>([])
  const [assistantPlaygroundIdParams, setAssistantPlaygroundIdParams] = useState('')
  const [topk, setTopk] = useState(3)
  const [maxTokens, setMaxToken] = useState(4096)
  const [viewCodeOpen, setViewCodeOpen] = useState(false)
  const [viewCodeData, setViewCodeData] = useState('')
  const [modelName, setModelName] = useState<any>('')
  const [selectedModelRows, setSelectedRows] = useState<any[]>([])
  const [selectedActionSelected, setSelectedActionSelected] = useState<any[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [recordsSelected, setRecordsSelected] = useState<string[]>([])

  useEffect(() => {
    const params = { limit: 20 }
    fetchActionsList(params)
    fetchModelsList()
    fetchDataRetrievalData(params)
    fetchViewCodeData()
  }, []);

  useEffect(() => {
    setAssistantPlaygroundIdParams(assistantPlaygroundId)
  }, [assistantPlaygroundId])

  useEffect(() => {
    if (users.data.length > 0) {
      setAssistantsList(users.data);
      setAssistantHasMore(users.has_more)
    } else {
      setAssistantsList([])
    }
    const data = retrievalLists.data.map((item: any) => {
      return {
        ...item,
        capacity1: item.num_chunks + '/' + item.capacity,
        key: item.collection_id,
      }
    })
    setRetrievalList(data);
    setBundlesList(pluginLists.data)
    setHasMore(retrievalLists.has_more)
  }, [users, retrievalLists, pluginLists]);

  const fetchViewCodeData = async () => {
    try {
      const res = await authService.getViewCode('assistant')
      setViewCodeData(res.data)
    } catch (error) {
      handleApiError(error)
    }
  }

  const handleViewCode = () => {
    setIsVisible(false)
    setViewCodeOpen(true)
  }

  const content = (
    <div style={{ cursor: 'pointer' }}>
      <p className={styles['popover-eidt']} onClick={handleViewCode}>View code</p>
      <p className={styles['popover-delete']} onClick={() => handleDelete(record as AssistantVM)} >Delete</p>
    </div>
  );

  const fetchData = async (params: { limit?: number }) => {
    try {
      const result = await assistantService.list(params)
      setAssistantsList(result.data);
      setAssistantHasMore(result.has_more)
    } catch (error) {
      handleApiError(error)
    }
  };

  const handleJump = (value: AssistantVM) => {
    dispatch(setPlaygroundSelect('assistant'))
    localStorage.setItem('assistantName', value.name)
    navigate(`/project/playground?assistant_id=${value.assistantId}`)
  }

  const handleModalClose = () => {
    setOriginalModelData((prev: any) => prev)
    setSelectedRows(originalModelData as any)
    setModalTableOpen(false)
  }

  const handleModalCloseConfirm = () => {
    if (selectedModelRows) {
      let str = selectedModelRows[0];
      let index = str.lastIndexOf('-');
      if (index !== -1) {
        let result = str.substring(0, index);
        setModelName(result)
      }
      setOriginalModelData(selectedModelRows)
    }
    setModalTableOpen(false)
  }

  const handleSchemaChange = (value: string) => {
    setSchema(value)
  }

  const handleActionRequest = async () => {
    if (!schema) {
      setTipSchema(true)
      return
    }
    const commonData: ActionBulkCreateRequest = {
      openapi_schema: JSON.parse(schema),
      authentication: {
        type: radioValue,
      } as any
    };
    if (radioValue === 'custom') {
      if (commonData.authentication) {
        (commonData.authentication as any).content = { [custom]: Authentication };
      }
    } else {
      if (radioValue === 'none') {
        (commonData.authentication as any).type = 'none'
      } else {
        if (commonData.authentication) {
          (commonData.authentication as any).secret = Authentication;
        }
      }
    }
    try {
      await actionService.bulkCreate(commonData);
      const params = { limit: 20 }
      await fetchActionsList(params, 'create');
    } catch (error) {
      handleApiError(error)
    } finally {
      setOpenActionDrawer(false)
    }
  }

  const fetchDataRetrievalData = async (params: any) => {
    try {
      dispatch(fetchRetrievalData(params) as any);
    } catch (e) {
      handleApiError(e)
    }
  }

  const handleInputPromptChange = (index: number, newValue: any) => {
    setSystemPromptTemplate((prevValues) =>
      prevValues.map((item, i) =>
        i === index ? newValue : item
      )
    );
  }

  const handleModalCancel = () => {
    setModelOne(false)
  }

  const handleSetModelConfirmOne = () => {
    setModelOne(false)
    setUpdateModelPrevButton(true)
  }

  const fetchActionsList = async (params: Record<string, string | number>, type?: string) => {
    if (type) {
      dispatch(fetchActionData(20) as any);
    }
    try {
      const result = await actionService.list(params)
      setActionList(result.data)
      setHasActionMore(result.has_more)
    } catch (error) {
      handleApiError(error)
    }
  }

  const handleCreateModelId = async () => {
    await setModelOne(true)
    childRef.current?.fetchAiModelsList()
    await fetchModelsList()
    setOptions(prevOptions => [...prevOptions]);
  }

  const handleCreatePrompt = () => {
    setDrawerTitle('Create Assistant')
    setAssistantId('')
    setSystemPromptTemplate([''])
    setSelectedPluginGroup([])
    setSelectedRetrievalRows([{ collection_id: '', id: '', name: '', type: 'collection' } as RetrievalRefVM])
    setSelectedActionsRows([{ type: 'plugin', value: '', name: '', id: '', typeLabel: 'Plugin' } as ToolRefVM])
    setSelectedActionSelected([])
    setDrawerName('')
    setSelectedRows([])
    setModelName(undefined)
    setMemoryValue('zero')
    setDrawerDesc('')
    setRecordsSelected([])
    setOpenDrawer(true)
    setIsVisible(false)
  }

  const handleEdit = (val: AssistantVM) => {
    setModelName(val.modelName)
    setDrawerTitle(`${t('projectEditAssistant')}`)
    setSelectedRetrievalRows(val.retrievals)
    setSelectedActionSelected(val.actionTools.map(item => ({
      action_id: item.id,
      name: item.name
    })))
    setSelectedPluginGroup(val.pluginTools.map(item => item.id?.split('/')[1]));
    setSelectedActionsRows(val.tools)
    setDrawerName(val.name)
    setDrawerDesc(val.description)
    setRetrievalConfig(val.retrievalConfigs.method)
    setTopk(val.retrievalConfigs.topK)
    setMaxToken(val.retrievalConfigs.maxTokens)
    setInputValueOne(val.memory.maxMessages)
    setInputValueTwo(val.memory.maxTokens)
    setMemoryValue(val.memory.type)
    setRecordsSelected([val.modelId])
    setAssistantId(val.assistantId)
    setSystemPromptTemplate(val.systemPromptTemplate)
    setSelectedRows([val.modelId])
    setOriginalModelData([val.modelId])
    setOpenDrawer(true)
    setIsVisible(false)
  }

  const handleDelete = (val: AssistantVM) => {
    setOpenDeleteModal(true)
    setIsVisible(false)
    setDeleteValue(val.name)
    setAssistantId(val.assistantId)
  }

  const onDeleteCancel = () => {
    setIsVisible(true)
    setOpenDeleteModal(false)
  }

  const handleRetrievalConfigChange1 = (value: string) => {
    setRetrievalConfig(value)
  }

  const onDeleteConfirm = async () => {
    const params = { limit: limit || 20 }
    setUpdatePrevButton(true)
    try {
      if (assistantId === assistantPlaygroundIdParams) {
        await dispatch(setPlaygroundAssistantId(''))
      }
      await assistantService.delete(assistantId)
      dispatch(fetchAssistantsData() as any)
      await fetchData(params)
      setOpenDeleteModal(false)
    } catch (error) {
      handleApiError(error)
    } finally {
      setIsVisible(true)
    }
  }

  const handleMemoryChange1 = (value: string) => {
    setMemoryValue(value)
  }

  const buildAssistantRequest = (): AssistantCreateRequest | AssistantUpdateRequest => {
    const inputValueMap = (drawerAssistantRef.current?.getRetrievalSelectedList() || []).map((item: any) => ({
      type: 'collection', id: item
    })).filter((item: any) => item.id)
    const inputPluginValues = (drawerAssistantRef.current?.getActionSelectedList() || [])
      .map((item: any) => ({ type: item.type, id: item.value }))
      .filter((item: any) => item.id)

    let systemTemplate: string[] = [];
    if (systemPromptTemplate.length === 1 && systemPromptTemplate[0] === '') {
      systemTemplate = []
    } else {
      systemTemplate = systemPromptTemplate
    }

    return {
      model_id: Array.isArray(originalModelData) ? originalModelData[0].slice(-8) : originalModelData,
      name: drawerName || '',
      description: drawerDesc || '',
      system_prompt_template: systemTemplate,
      tools: inputPluginValues,
      retrievals: inputValueMap,
      memory: {
        type: memoryValue as any,
        max_messages: Number(inputValueOne) || undefined,
        max_tokens: Number(inputValueTwo) || undefined
      },
      retrieval_configs: {
        top_k: Number(topk) || undefined,
        method: retrievalConfig as any,
        max_tokens: Number(maxTokens) || undefined
      }
    }
  }

  const handleRequest = async () => {
    const params = buildAssistantRequest();
    let count = 0
    systemPromptTemplate.forEach(item => { count += item.length })
    if (count > 16384) {
      return toast.error(`${t('projectAssistantSystemPromptRequired')}`)
    }
    const modelId = Array.isArray(originalModelData) ? originalModelData[0] : originalModelData
    if (!modelId || String(modelId).slice(-8).length !== 8) {
      return toast.error(`${t('projectAssistantModelIDRequired')}`)
    }
    if (!originalModelData || (Array.isArray(originalModelData) && originalModelData.length === 0)) {
      return toast.error(`${t('projectModelRequired')}`)
    }
    try {
      setLoading(true)
      if (assistantId) {
        await assistantService.update(assistantId, params as AssistantUpdateRequest)
      } else {
        await assistantService.create(params as AssistantCreateRequest)
      }
      setOpenDrawer(false)
      const params1 = { limit: limit || 20 }
      await fetchData(params1)
      dispatch(fetchAssistantsData() as any)
      setUpdatePrevButton(true)
    } catch (error) {
      handleApiError(error)
    } finally {
      setLoading(false)
      setIsVisible(true)
    }
  }

  const fetchModelsList = async (value?: any, type?: string) => {
    if (type) {
      dispatch(fetchModelsData(20) as any);
    }
    const params = {
      limit: modelLimit || 20,
      ...value
    }
    try {
      const result = await modelService.listByType('chat_completion', params)
      setOptions(result.data)
      setHasModelMore(result.has_more)
    } catch (error) {
      handleApiError(error)
    }
  }

  const handleCancel = () => {
    setOpenDrawer(false)
    setIsVisible(true)
  }

  const handleChildEvent = async (value: valueLimit) => {
    setLimit(value.limit)
    setUpdatePrevButton(false)
    await fetchData(value);
  }

  const handleDeletePromptInput = (index: number) => {
    const updatedInputValues = [...systemPromptTemplate];
    updatedInputValues.splice(index, 1);
    setSystemPromptTemplate(updatedInputValues);
  }

  const handleNewCollection = (value: boolean) => {
    setOpenCollectionDrawer(value)
  }

  const hangleChangeAuthorization = (value: string) => {
    setAuthentication(value)
  }

  const handleAddPrompt = () => {
    if (systemPromptTemplate.length < 10) {
      setSystemPromptTemplate((prevValues => [...prevValues, '']))
    }
  }

  const handleSelectModelId = (value: boolean) => {
    setModalTableOpen(value)
  }

  const handleChildModelEvent = async (value: valueLimit) => {
    setModelLimit(value.limit)
    setUpdateModelPrevButton(false)
    await fetchModelsList(value)
  }

  const handleChangeName = (value: string) => {
    setDrawerName(value)
  }

  const handleInputValueOne = (value: number) => {
    setInputValueOne(value)
  }

  const handleInputValueTwo = (value: number) => {
    setInputValueTwo(value)
  }

  const handleDescriptionChange = (value: string) => {
    setDrawerDesc(value)
  }

  const onRadioChange = (value: string) => {
    setRadioValue(value)
  }

  const handleActionCancel = () => {
    setOpenActionDrawer(false)
  }

  const handleRecordsSelected = (value: any, selectedRows: any[]) => {
    setRecordsSelected(value)
    const tag = selectedRows.map(item => (item.name + '-' + item.model_id))
    setSelectedRows(tag)
  }

  const handleCustom = (value: string) => {
    setCustom(value)
  }

  const onhandleTipError = (value: boolean) => {
    setTipSchema(value)
  }

  const handleClosePluginModal = () => {
    setPluginModalOpen(false)
  }

  const handleConfirmRequest = async () => {
    dispatch(fetchPluginData(20) as any);
  }

  const handleNewActionModal = () => {
    setOpenActionDrawer(true)
  }

  const handleMaxToken = (value: any) => {
    setMaxToken(value)
  }

  const handleToks = (value: any) => {
    setTopk(value)
  }

  const handleNewBundle = () => {
    setPluginModalOpen(true)
  }

  const handleCloseViewCode = () => {
    setIsVisible(true)
    setViewCodeOpen(false)
  }

  return (
    <div className={styles["assistants"]}>
      <Spin spinning={loading} wrapperClassName={styles.spinloading}>
        <ModalTable title='New assistant' loading={loading} updatePrevButton={updatePrevButton} hasMore={assistantHasMore} id="assistant_id" ifSelect={false} columns={columns} name="assistant" dataSource={assistantsList} onChildEvent={handleChildEvent} onOpenDrawer={handleCreatePrompt} />
      </Spin>
      <Drawer
        className={styles['drawer-assistants']}
        width={1280}
        closeIcon={<img src={closeIcon} alt="closeIcon" className={styles['img-icon-close']} />}
        onClose={handleCancel} title={drawerTitle} placement="right" open={OpenDrawer} size='large' footer={[
          <Button key="cancel" onClick={handleCancel} className='cancel-button'>
            {t('cancel')}
          </Button>,
          <Button key="submit" loading={editLoading} onClick={handleRequest} className={`next-button ${styles['button']}`}>
            {t('confirm')}
          </Button>
        ]}>
        <DrawerAssistant modelName={modelName} drawerTitle={drawerTitle} openDrawer={OpenDrawer} selectedActionsSelected={selectedActionSelected} selectedPluginGroup={selectedPluginGroup} handleNewBundle={handleNewBundle} retrievalConfig={retrievalConfig} topk={topk} maxTokens={maxTokens} handleMaxToken={handleMaxToken} handleToks={handleToks} bundilesList={bundilesList} handleNewActionModal={handleNewActionModal} handleNewCollection={handleNewCollection} selectedCollectionList={selectedRetrievalRows} actionHasMore={hasActionMore} actionList={actionList} collectionHasMore={hasMore} ref={drawerAssistantRef}
          handleRetrievalConfigChange1={handleRetrievalConfigChange1} retrievalList={retrievalList} selectedActionsRows={selectedActionsRows} inputValue1={inputValueOne} inputValue2={inputValueTwo} handleMemoryChange1={handleMemoryChange1} memoryValue={memoryValue} handleAddPromptInput={handleAddPrompt} drawerName={drawerName} systemPromptTemplate={systemPromptTemplate} handleDeletePromptInput={handleDeletePromptInput} handleInputPromptChange={handleInputPromptChange} handleInputValueOne={handleInputValueOne} handleInputValueTwo={handleInputValueTwo} selectedRows={originalModelData} handleSelectModelId={handleSelectModelId} handleChangeName={handleChangeName} drawerDesc={drawerDesc} handleDescriptionChange={handleDescriptionChange}  ></DrawerAssistant>
      </Drawer>

      <ModelModal type='chat_completion' ref={childRef} open={modelOne} handleSetModelConfirmOne={handleSetModelConfirmOne} handleSetModelOne={handleModalCancel} getOptionsList={fetchModelsList} modelType='chat_completion'></ModelModal>
      <Modal closeIcon={<img src={closeIcon} alt="closeIcon" className={styles['img-icon-close']} />} centered onCancel={handleModalClose} footer={[
        <div className='footer-group' key='footer1'>
          <Button key="model" icon={<PlusOutlined />} onClick={handleCreateModelId} className='cancel-button'>
            {t('projectNewModel')}
          </Button>
          <div>
            <span className='select-record'>
              {recordsSelected.length}  {recordsSelected.length > 1 ? `${t('projectItemsSelected')}` : `${t('projectItemSelected')}`}
            </span>
            <Button key="cancel" onClick={handleModalClose} className={`cancel-button ${styles.cancelButton}`}>
              {t('cancel')}
            </Button>
            <Button key="submit" onClick={handleModalCloseConfirm} className='next-button'>
              {t('confirm')}
            </Button>
          </div>
        </div>
      ]} title={t('projectSelectModel')} open={modalTableOpen} width={1000} className={`modal-inner-table ${styles['retrieval-model']}`}>
        <ModalTable title='New model' onOpenDrawer={handleCreateModelId} name="model" updatePrevButton={updateModelPrevButton} defaultSelectedRowKeys={selectedModelRows} handleRecordsSelected={handleRecordsSelected} ifSelect={true} columns={modelsTableColumn} hasMore={hasModelMore} id='model_id' dataSource={options} onChildEvent={handleChildModelEvent}></ModalTable>
      </Modal>
      <ViewCode open={viewCodeOpen} data={viewCodeData} handleClose={handleCloseViewCode} />
      <CreatePlugin handleConfirmRequest={handleConfirmRequest} open={pluginModalOpen} handleCloseModal={handleClosePluginModal}></CreatePlugin>
      <DeleteModal open={OpenDeleteModal} describe={`${t('deleteItem')} ${deleteValue || 'Untitled Assistant'}? This action cannot be undone and all integrations associated with the assistant will be affected.`} title='Delete Assistant' projectName={deleteValue || 'Untitled Assistant'} onDeleteCancel={onDeleteCancel} onDeleteConfirm={onDeleteConfirm} />
      <Drawer zIndex={10001} className={styles['drawer-action']} closeIcon={<img src={closeIcon} alt="closeIcon" className={styles['img-icon-close']} />} onClose={handleActionCancel} title='Bulk Create Action' placement="right" open={OpenActionDrawer} size='large' footer={<ModalFooterEnd handleOk={() => handleActionRequest()} onCancel={handleActionCancel} />}>
        <ActionDrawer showTipError={tipSchema} onhandleTipError={onhandleTipError} schema={schema} onSchemaChange={handleSchemaChange} onRadioChange={onRadioChange} onChangeCustom={handleCustom} onChangeAuthentication={hangleChangeAuthorization} radioValue={radioValue} custom={custom} Authentication={Authentication} />
      </Drawer>
      <CreateCollection handleFetchData={() => fetchDataRetrievalData({ limit: 20 })} handleModalCloseOrOpen={() => setOpenCollectionDrawer(false)} OpenDrawer={openCollectionDrawer}></CreateCollection>
    </div>)
}

export default AssistantRefactored
