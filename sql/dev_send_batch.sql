ALTER TABLE `dev_send_batch`
    ADD COLUMN `send_type` varchar(20) DEFAULT 'IMMEDIATE' COMMENT '下发方式：IMMEDIATE/APPOINT',
    ADD COLUMN `appoint_time` bigint DEFAULT NULL COMMENT '预约下发时间(毫秒)',
    ADD COLUMN `notice_email_sent` tinyint(1) DEFAULT 0 COMMENT '下发结果邮件是否已发送';

ALTER TABLE `dev_send_batch_log`
    ADD COLUMN `send_type` varchar(20) DEFAULT 'IMMEDIATE' COMMENT '下发方式：IMMEDIATE/APPOINT';