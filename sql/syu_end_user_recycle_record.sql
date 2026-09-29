SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for syu_end_user_recycle_record
-- ----------------------------
DROP TABLE IF EXISTS `syu_end_user_recycle_record`;
CREATE TABLE `syu_end_user_recycle_record`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `parent_org_id` int(0) NOT NULL COMMENT '父归属机构id（操作机构）',
  `industry_scene_id` int(0) NOT NULL COMMENT '行业场景id',
  `target_org_id` int(0) NOT NULL COMMENT '回收目标机构id',
  `recycle_from_org_id` int(0) NULL DEFAULT NULL COMMENT '回收来源机构id（取首个回收用户原父机构）',
  `total_count` int(0) NOT NULL DEFAULT 0 COMMENT '回收总数',
  `success_count` int(0) NOT NULL DEFAULT 0 COMMENT '回收成功数',
  `fail_count` int(0) NOT NULL DEFAULT 0 COMMENT '回收失败数',
  `recycle_time` bigint(0) NOT NULL COMMENT '回收时间（时间戳，毫秒）',
  `create_time` bigint(0) NOT NULL COMMENT '创建时间（时间戳，毫秒）',
  `operator_user_id` int(0) NOT NULL COMMENT '操作人id',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_parent_org_scene_time`(`parent_org_id`, `industry_scene_id`, `recycle_time`) USING BTREE,
  INDEX `idx_target_org_time`(`target_org_id`, `recycle_time`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 26 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '终端用户回收记录表' ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;


-- -- ----------------------------
-- -- Rollback script for syu_end_user_recycle_record
-- -- ----------------------------
-- DROP TABLE IF EXISTS `syu_end_user_recycle_record`;
