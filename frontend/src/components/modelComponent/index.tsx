import {
    Button,
    Modal
} from 'antd';
import closeIcon from '../../assets/img/x-close.svg'
import { PlusOutlined } from '@ant-design/icons';
import { useTranslation } from "react-i18next";
import { useEffect, useState, useRef, useMemo } from 'react'
import ModelModal from '../modelModal/index'
import { ChildRefType } from '../../constant/index.ts'
import ModalTable from '../modalTable/index'
import { getModelsList, evaluateModelCapabilities } from '../../axios/models.ts'
import { useDispatch } from 'react-redux';
import { fetchModelsData } from '../../Redux/actions.ts'
import { valueLimit, } from '@/constant/assistant.ts'
import CommonComponents from '../../contents/index'
import styles from './modelComponent.module.scss'
import { toast } from 'react-toastify'
import type { CapabilityRequirement, CapabilityEvaluationResultItem, RecordType } from '@/constant/index.ts'
function ModelComponent(props: any) {
    const { t } = useTranslation();
    const dispatch = useDispatch();
    const { modelsTableColumn,  } = CommonComponents();
    const [recordsSelected, setRecordsSelected] = useState([])
    const [confirmLoading, setConfirmLoading] = useState(false)
    const [modelOne, setModelOne] = useState(false);
    const childRef = useRef<ChildRefType | null>(null);
    const [updateModelPrevButton, setUpdateModelPrevButton] = useState(false)
    const [options, setOptions] = useState<RecordType[]>([])
    const [hasModelMore, setHasModelMore] = useState(false)
    const [modelLimit, setModelLimit] = useState(20)
    const [selectedRows, setSelectedRows] = useState<any[]>([])
    const [detailSelectedRowInfo, setDetailSelectedRowInfo] = useState<any>({})
    const [evaluationsByModelId, setEvaluationsByModelId] = useState<Record<string, CapabilityEvaluationResultItem>>({})
    const [evaluating, setEvaluating] = useState(false)

    const capabilityRequirement: CapabilityRequirement | undefined = props.capabilityRequirement

    useEffect(() => {
        fetchModelsList()
    }, [])

    useEffect(() => {
        if (capabilityRequirement && options.length > 0) {
            runCapabilityEvaluation(options)
        } else {
            setEvaluationsByModelId({})
        }
    }, [capabilityRequirement])

    useEffect(() => {
        setSelectedRows(props.defaultSelectedData || [])
    }, [props.defaultSelectedData])

    const runCapabilityEvaluation = async (models: RecordType[]) => {
        if (!capabilityRequirement || models.length === 0) {
            setEvaluationsByModelId({})
            return
        }
        setEvaluating(true)
        try {
            const modelIds = models.map(m => m.model_id)
            const evalRes = await evaluateModelCapabilities(capabilityRequirement, modelIds)
            const evalData: CapabilityEvaluationResultItem[] = evalRes.data || []
            const map: Record<string, CapabilityEvaluationResultItem> = {}
            evalData.forEach(item => {
                map[item.model_id] = item
            })
            setEvaluationsByModelId(map)
        } catch (e) {
            console.error('Capability evaluation failed:', e)
        } finally {
            setEvaluating(false)
        }
    }

    const optionsWithEvaluation: RecordType[] = useMemo(() => {
        return options.map(opt => {
            const evalItem = evaluationsByModelId[opt.model_id]
            if (!evalItem) return opt
            return {
                ...opt,
                _evaluation: evalItem,
            }
        })
    }, [options, evaluationsByModelId])
    const handleCreateModelId = async () => {
        await setModelOne(true)
        childRef.current?.fetchAiModelsList()

    }
    const handleSetModelConfirmOne = () => {
        setModelOne(false)
        setUpdateModelPrevButton(true)
    }
    const handleModalCancel = () => {
        setModelOne(false)
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
            const res: any = await getModelsList(params, 'chat_completion')
            const data: RecordType[] = res.data.map((item: any) => {
                return {
                    ...item,
                    key: item.model_id
                }
            })
            setOptions(data)
            setHasModelMore(res.has_more)
            if (capabilityRequirement && data.length > 0) {
                await runCapabilityEvaluation(data)
            }
        } catch (error) {
            console.log(error)
        }
    }
    const handleModalClose = () => {
       props.handleCloseModal()
    }
    const handleChildModelEvent = async (value: valueLimit) => {
        setModelLimit(value.limit)
        setUpdateModelPrevButton(false)
        await fetchModelsList(value)
    }
    const handleRecordsSelected = (value: any, selectedRows: any[]) => {
        setRecordsSelected(value)
        setDetailSelectedRowInfo(selectedRows)
        const tag = selectedRows.map(item => (item.name + '-' + item.model_id))
        setSelectedRows(tag)
    }
    const handleModalConfirm =async () => {
        if (capabilityRequirement && detailSelectedRowInfo?.length > 0) {
            const selected = detailSelectedRowInfo[0] as RecordType
            const evalItem = selected?._evaluation || evaluationsByModelId[selected?.model_id]
            if (evalItem && !evalItem.is_compatible && evalItem.incompatibility_reasons?.length > 0) {
                const first = evalItem.incompatibility_reasons[0]
                toast.error(first.reason, { autoClose: 10000 })
                return
            }
        }
        setConfirmLoading(true)
        await props.handleModalConfirm(...detailSelectedRowInfo)
        setConfirmLoading(false)
    }
    return (
        <>
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
                        <Button key="submit" onClick={handleModalConfirm} className='next-button' loading={confirmLoading}>
                            {t('confirm')}
                        </Button>
                    </div>
                </div>
            ]} title={t('projectSelectModel')} open={props.modalTableOpen} width={1000} className={`modal-inner-table ${styles['retrieval-model']}`}>
                <ModalTable onOpenDrawer={handleCreateModelId} title='New model' name="model" updatePrevButton={updateModelPrevButton} defaultSelectedRowKeys={selectedRows} handleRecordsSelected={handleRecordsSelected} ifSelect={true} columns={modelsTableColumn} hasMore={hasModelMore} id='model_id' dataSource={optionsWithEvaluation} onChildEvent={handleChildModelEvent} capabilityRequirement={capabilityRequirement}></ModalTable>
            </Modal>
            <ModelModal type='chat_completion' ref={childRef} open={modelOne} handleSetModelConfirmOne={handleSetModelConfirmOne} handleSetModelOne={handleModalCancel} getOptionsList={fetchModelsList} modelType='chat_completion'></ModelModal>
        </>


    );
}
export default ModelComponent;