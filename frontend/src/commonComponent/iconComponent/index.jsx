import React, { useEffect, useState } from 'react';
import { authService } from '@/api';
import styles from './icon.module.scss'
const IconComponent = ({ providerId }) => {
    const [iconHtml, setIconHtml] = useState('');
    useEffect(() => {
        const fetchIcon1 = async () => {
            const html = await authService.fetchIcon(providerId)
            setIconHtml(html);
        };

        fetchIcon1()
    }, [providerId]);
    return <div dangerouslySetInnerHTML={{ __html: iconHtml }} className={styles.icon} />;
};

export default IconComponent;
