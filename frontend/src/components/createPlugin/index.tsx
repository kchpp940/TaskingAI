import { Modal, Button, Spin, Form, Input } from 'antd';
import { useState, useEffect,useImperativeHandle, forwardRef } from 'react';
import { useTranslation } from 'react-i18next';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import styles from './createPlugin.module.scss';
import closeIcon from '../../assets/img/x-close.svg'
import { pluginService, handleApiError } from '@/api'
import type { BundleVM, PluginVM } from '@/api'
import ParameterTable from '../parameterTable/index.tsx'
import RightArrow from '../../assets/img/rightarrow.svg?react'
import ToolsNew from '../../assets/img/tools.svg?react'
import { toast } from 'react-toastify';

const CreatePlugin = forwardRef((props:any, ref) => {

    const { t } = useTranslation();
    const { open, handleCloseModal, handleConfirmRequest } = props
    const [openCreateModal2, setOpenCreateModal2] = useState(false);
    const [openCreateModal3, setOpenCreateModal3] = useState(false);
    const [confirmLoading, setConfirmLoading] = useState(false)
    const [form] = Form.useForm();
    const [bundleId, setBundleId] = useState('')
    const [bundilesList, setBundlesList] = useState([])
    const [nextLoading1, setNextLoading1] = useState(false)
    const [pluginName, setPluginName] = useState('')
    const [credentialsSchema, setCredentialsSchema] = useState({})
    const [pluginInfoLoading, setPluginInfoLoading] = useState(false)
    const [bundleName, setBundleName] = useState('')
    const [pluginListData, setPluginListData] = useState([])
    const [pluginId, setPluginId] = useState('')
    const [pluginDesc, setPluginDesc] = useState('')
    const [description,setDescription] = useState('')
    const [inputSchema, setInputSchema] = useState({})
    const [cachedImages, setCachedImages] = useState({});

    useEffect(() => {
        const params1 = {
            limit: 100,
            offset: 0,
            lang: 'en'
        }
        getBundleList(params1)
    }, [])
    useImperativeHandle(ref, () => ({
        getBundleList: getBundleList
    }));
    const getBundleList = async (params: object) => {
        const res = await pluginService.listBundles(params as any)
        const selectedItem = res.data.find((item: BundleVM) => item.registered === false) || res.data[0]
        setBundleId(selectedItem.bundleId)
        setBundleName(selectedItem.name)
        setDescription(selectedItem.description)
        setBundlesList(res.data)
        const imagesData: Record<string, string> = {};
        res.data.forEach((bundle) => {
            if (bundle.iconUrl) {
                fetch(bundle.iconUrl)
                    .then(response => response.blob())
                    .then(blob => {
                        const reader = new FileReader();
                        reader.onload = function () {
                            imagesData[bundle.bundleId] = reader.result as string;
                            setCachedImages({...imagesData});
                        };
                        reader.readAsDataURL(blob);
                    });
            }
        });
        setCredentialsSchema(selectedItem.credentialsSchema || {})
        const plugins = await pluginService.getBundlePlugins(selectedItem.bundleId)
        setPluginListData(plugins)
        if (plugins.length > 0) {
            setPluginId(plugins[0].pluginId)
            setPluginName(plugins[0].name)
            setPluginDesc(plugins[0].description)
            setInputSchema(plugins[0].inputSchema)
        }
    }

    const handleNext1 = async () => {
        if (JSON.stringify(credentialsSchema) === '{}') {
            const params = {
                name: bundleName,
                bundle_id: bundleId,
            }
            try {
                setNextLoading1(true)
                await pluginService.createBundleInstance(params)
                const params1 = {
                    limit: 100,
                    offset: 0,
                    lang: 'en'
                }
                await getBundleList(params1)
                handleConfirmRequest()
                handleCloseModal()
                setOpenCreateModal3(false)
                setOpenCreateModal2(false)
                toast.success('Creation successful!')
            } catch (e) {
                handleApiError(e)
            } finally {
                setNextLoading1(false)
            }
        } else {
            form.resetFields()
            setOpenCreateModal3(true)
        }
    }
    const handleCancel1 = () => {
        setOpenCreateModal2(false)
    }
    const handleCancel = () => {
        handleCloseModal()
    }
    const handleNext = () => {
        setOpenCreateModal2(true)
    }
    const handleCancel2 = () => {
        setOpenCreateModal3(false)
    }
    const handleConfirm = async () => {
        form.validateFields().then(async () => {
            try {
                const credentials = form.getFieldsValue()
                const params = {
                    name: bundleName,
                    credentials,
                    bundle_id: bundleId,
                }
                setConfirmLoading(true)
                await pluginService.createBundleInstance(params)
                const params1 = {
                    limit: 100,
                    offset: 0,
                    lang: 'en'
                }
                await getBundleList(params1)
                handleConfirmRequest()
                setOpenCreateModal3(false)
                setOpenCreateModal2(false)
                handleCloseModal()

                toast.success('Creation successful!')
            } catch (error) {
                handleApiError(error)
            } finally {
                setConfirmLoading(false)
            }
        })

    }
    const handleValuesChange = (changedValues: object) => {
        form.validateFields(Object.keys(changedValues));
    };
    const handleClickPlugin = (pluginId: string, pluginName: string) => {
        setPluginId(pluginId)
        setPluginName(pluginName)
        const plugin = (pluginListData as PluginVM[]).find(item => item.pluginId === pluginId)
        if (plugin) {
            setPluginDesc(plugin.description)
            setInputSchema(plugin.inputSchema)
        }
    }
    const handleClickBundle = async (bundleId: string, bundleName: string, item: any) => {
        setBundleId(bundleId)
        setPluginInfoLoading(true)
        setBundleName(bundleName)
        setDescription(item.description)
        setCredentialsSchema(item.credentialsSchema || {})
        setPluginListData(item.plugins || [])
        if (item.plugins && item.plugins.length > 0) {
            setPluginId(item.plugins[0].pluginId)
            setPluginName(item.plugins[0].name)
            setPluginDesc(item.plugins[0].description)
            setInputSchema(item.plugins[0].inputSchema)
        }
        setPluginInfoLoading(false)
    }
    return <>
        <Modal footer={[
            <>
                {openCreateModal2 ? <>
                    <Button icon={<LeftOutlined />} key="cancel" onClick={handleCancel1} className='cancel-button'>
                        {t('back')}
                    </Button>
                    <Button key="submit" onClick={handleNext1} loading={nextLoading1} className='next-button' style={{ marginLeft: '10px' }}>
                        {t('confirm')}
                    </Button>
                </> : <><Button key="cancel" onClick={handleCancel} className='cancel-button'>
                    {t('cancel')}
                </Button>
                    <Button key="submit" onClick={handleNext} className='next-button' style={{ marginLeft: '10px' }}>
                        {t('next')}
                        <RightOutlined />
                    </Button></>}
            </>
        ]} zIndex={10002} width={1280} onCancel={handleCancel} centered closeIcon={<img src={closeIcon} alt="closeIcon" className={styles['img-icon-close']} />} title={openCreateModal2 ? t('projectPluginCreate') : t('projectBundleSelection')} open={open} className={styles.drawerCreate}>
            {openCreateModal2 ? <div className={styles.componentsData}>
                <div className={styles.inputWithLabelParent}>
                    <div className={styles.inputWithLabel}>
                        <div className={styles.label}>{t('projectBundleTitle')}</div>
                        <div className={styles.inputWithLabelInner}>
                            <div className={styles.frameWrapper}>
                                <div className={styles.frameContainer}>
                                    <div className={styles.logoParent}>
                                        <img loading="lazy" src={(cachedImages as any)[bundleId]} alt="" style={{ width: '24px', height: '24px' }} />
                                        <div className={styles.label}>{bundleName}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className={styles.content1}>
                    <div className={styles.left}>
                        {pluginListData.map((item: any, index) => (
                            <div key={index} onClick={() => { handleClickPlugin(item.pluginId, item.name) }} className={`${styles.pluginName} ${pluginId === item.pluginId && styles.pluginId}`}>
                                {item.name}
                            </div>
                        ))}
                    </div>
                    <div className={styles.right}>
                        <div className={styles.topContent}>
                            <div className={styles.pluginTitle}>{pluginName}</div>


                        </div>
                        <div className={styles.pluginDesc}>{pluginDesc}</div>
                        <div className={styles.inputParams}>{t('projectInputParameters')}</div>
                        <div style={{ marginLeft: '24px', marginTop: '12px' }}>
                            <ParameterTable parameters={inputSchema} />
                        </div>
                    </div>
                </div></div> : <div className={styles.modalContent}>
                <div className={styles.left}>
                    <div className={styles.selectBundleDesc}>{t('projectBundleDesc')}</div>
                    <div className={styles['content-modal']}>
                        <div className={styles.content}>
                            {bundilesList.map((item: any, index: number) => (
                                <div key={index} className={`${styles.frameParent} ${item.bundleId === bundleId && styles.activeframeParent} ${item.registered && styles.registeredItem}`} onClick={item.registered ? undefined : () => { handleClickBundle(item.bundleId, item.name, item) }}>
                                    <div className={styles.logoParent}>
                                        <img src={(cachedImages as any)[item.bundleId]} alt="" className={styles.img} />
                                        <div className={styles.frameWrapper}>
                                            <div className={styles.frameWrapper}>
                                                <div className={styles.frameDiv}>
                                                    <div className={styles.frameChild} />
                                                </div>
                                            </div>
                                        </div>
                                        {item.registered ? <div className={styles.registered}>Registered</div> : <RightArrow />}
                                    </div>
                                    <div className={styles.googleWebSearch}>{item.name}</div>
                                    <div className={styles.label}>{item.description}</div>

                                    <div className={styles.frameGroup}>
                                        <div className={styles.functionaliconsParent}>
                                            <ToolsNew />
                                            <div className={styles.webSearch}>{item.numPlugins} {item.numPlugins > 1 ? t('projectToolsTitle') : 'Tool'}</div>
                                        </div>
                                        <div className={styles.taskingaiWrapper}>
                                            <div className={styles.taskingai}>{item.developer}</div>
                                        </div>
                                    </div>
                                </div>
                            ))}

                        </div>
                    </div>

                </div>
                <Spin spinning={pluginInfoLoading}>
                    <div className={styles.popupbodynormal}>
                        <div className={styles.googleWeb}>
                            <img loading="lazy" src={(cachedImages as any)[bundleId]} alt="" style={{ width: '36px', height: '36px' }} />
                            <div className={styles.googleWebSearch1}>{bundleName}</div>
                        </div>
                        <div className={styles['description-bundle']}>
                            <div className={styles['desc-title']}>Description</div>
                            <div className={styles['description-detail']}>{description}</div>
                        </div>
                        <div className={styles['description-bundle']}>
                            <div className={styles['desc-title']}>Plugins</div>
                            {
                                pluginListData.map((item: any, index) => (
                                    <div className={styles.pluginContent} key={index}>
                                        <div className={styles.pluginTitle}>{item.name}</div>
                                        <div className={styles.pluginDesc}>
                                            {item.description}
                                        </div>
                                    </div>
                                ))
                            }
                        </div>
                    </div>
                </Spin>
            </div>}
        </Modal>
        <Modal footer={[
            <Button key="cancel" onClick={handleCancel2} className='cancel-button'>
                {t('cancel')}
            </Button>,
            <Button key="submit" loading={confirmLoading} onClick={handleConfirm} className='next-button'>
                {t('confirm')}
            </Button>
        ]} width={720} zIndex={10003} onCancel={handleCancel2} open={openCreateModal3} centered closeIcon={<img src={closeIcon} alt="closeIcon" className={styles['img-icon-close']} />} title={t('projectPluginCreate')} className={styles.createModal3}>
            <div className={styles.editForm}>
                <div className={styles.bundleTitle}>
                    <div className={styles.label}>{t('projectBundleTitle')}</div>
                    <div className={styles.googleWeb}>
                        <img loading="lazy" src={(cachedImages as any)[bundleId]} alt="" style={{ width: '24px', height: '24px' }} />
                        <div className={styles.googleWebSearch}>{bundleName}</div>
                    </div>
                </div>
                <div className={styles['credentials']}>{t('projectModelCredentials')}</div>
                <div className={styles['label-desc']} style={{ marginBottom: '24px' }}>
                    All plugin credentials are encrypted at rest with AES-256 and in transit with TLS 1.2.
                </div>

                <Form
                    layout="vertical"
                    autoComplete="off"
                    form={form}
                    onValuesChange={handleValuesChange}
                    className={styles['second-form']}
                >
                    {credentialsSchema && Object.entries(credentialsSchema).map(([key, property]: [any, any]) => (
                        <Form.Item label={key} key={key} name={key} rules={[
                            {
                                required: property.required,
                                message: `Please input ${key}.`,
                            },
                        ]}>
                            <div className={styles['description']}>{(property as { description: string }).description}</div>
                            <Form.Item
                                name={key}
                                key={key}
                                className={styles['form-item']}
                            >
                                <Input placeholder={`Enter ${key}`} className={styles['input']} />
                            </Form.Item>
                        </Form.Item>
                    ))}
                </Form>
            </div>
        </Modal>
    </>;
})
export default CreatePlugin;