
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for syu_ble_role_level_config
-- ----------------------------
DROP TABLE IF EXISTS `syu_ble_role_level_config`;
CREATE TABLE `syu_ble_role_level_config`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `role_id` int(0) NOT NULL COMMENT '角色ID',
  `industry_scene_id` int(0) NULL DEFAULT NULL COMMENT '行业场景ID',
  `level_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '蓝牙权限级别编码，例如 LEVEL_1 / LEVEL_2 / LEVEL_3',
  `enabled` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用 1-启用 0-停用',
  `valid_to` bigint(0) NULL DEFAULT NULL COMMENT '失效时间戳(ms)，为空且enabled=1表示常开',
  `ts_create_time` bigint(0) NOT NULL COMMENT '创建时间戳(ms)',
  `ts_update_time` bigint(0) NOT NULL COMMENT '更新时间戳(ms)',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_role_scene_level`(`role_id`, `industry_scene_id`, `level_code`) USING BTREE,
  INDEX `idx_industry_scene_id`(`industry_scene_id`) USING BTREE,
  INDEX `idx_valid_to`(`valid_to`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 68 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '角色蓝牙级别权限配置' ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- Rollback script
-- ----------------------------
-- DROP TABLE IF EXISTS `syu_ble_role_level_config`;