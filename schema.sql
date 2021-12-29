DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` bigint NOT NULL,
  `joined_user_count` bigint NOT NULL,
  `status` int NOT NULL DEFAULT 1,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_user`;
CREATE TABLE `room_user` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `live_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);
