SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for syu_end_user_assign_detail
-- ----------------------------
DROP TABLE IF EXISTS `syu_end_user_assign_detail`;
CREATE TABLE `syu_end_user_assign_detail`  (
  `id` bigint(0) UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `record_id` bigint(0) UNSIGNED NOT NULL COMMENT '分配记录id',
  `from_org_id` int(0) NULL DEFAULT NULL COMMENT '归属终端机构id（原终端机构）',
  `target_org_id` int(0) NOT NULL COMMENT '目标机构id',
  `new_parent_org_id` int(0) NOT NULL COMMENT '新父机构id（与目标机构一致）',
  `user_id` int(0) NOT NULL COMMENT '终端用户id',
  `status` tinyint(0) NOT NULL COMMENT '状态：0-成功 1-失败',
  `fail_reason` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '失败原因',
  `assign_time` bigint(0) NOT NULL COMMENT '分配时间（时间戳，毫秒）',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_record`(`record_id`) USING BTREE,
  INDEX `idx_user`(`user_id`) USING BTREE,
  INDEX `idx_org_time`(`from_org_id`, `target_org_id`, `assign_time`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 31 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '终端用户分配记录详情表' ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- Rollback script
-- ----------------------------
-- DROP TABLE IF EXISTS `syu_end_user_assign_detail`;