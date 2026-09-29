CREATE TABLE `syu_role_product_label`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `role_id` int(0) NOT NULL COMMENT '角色ID',
  `industry_scene_id` int(0) NOT NULL DEFAULT 0 COMMENT '行业场景ID',
  `product_id` int(0) NOT NULL COMMENT '产品ID',
  `label_id` int(0) NOT NULL COMMENT '标签ID',
  `create_by` int(0) NULL DEFAULT NULL COMMENT '创建人',
  `create_time` bigint(0) NULL DEFAULT NULL COMMENT '创建时间（时间戳）',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_scene_role_product_label`(`industry_scene_id`, `role_id`, `product_id`, `label_id`) USING BTREE,
  INDEX `idx_scene_product_label`(`industry_scene_id`, `product_id`, `label_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '角色-产品-标签绑定表（按行业场景隔离）' ROW_FORMAT = Dynamic;
