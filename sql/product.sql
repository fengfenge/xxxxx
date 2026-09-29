-- 将 prd_tsl_label 与开发环境对齐：补充 label_tsl、ts_update_time（列顺序与开发一致）
ALTER TABLE `prd_tsl_label`
  ADD COLUMN `label_tsl` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NULL COMMENT 'tsl json定义' AFTER `create_time`,
  ADD COLUMN `ts_update_time` bigint(0) NULL DEFAULT NULL COMMENT '最后更新时间（时间戳）' AFTER `label_tsl`;

-- prd_tsl_prop_cfg 与开发对齐：增加 tsl_label_id
ALTER TABLE `prd_tsl_prop_cfg`
  ADD COLUMN `tsl_label_id` int(0) NULL DEFAULT NULL COMMENT '标签ID，NULL为默认配置' AFTER `product_id`;
  
  