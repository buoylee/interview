-- 支撑 ch05/06/07/08 scenario 的演示表与存储过程。
-- 只建结构、不灌数据；需要数据量的 scenario 自己 CALL seed()/flood()。
-- (sbtest1 / user_profile 在 01-create-schema.sql；这里补 scenario 专用对象。)

USE sbtest;

-- ch05 MVCC：小账户表 + 制造 undo 版本的洪流过程
CREATE TABLE IF NOT EXISTS mvcc_demo (
  id INT PRIMARY KEY,
  name VARCHAR(32),
  balance INT
) ENGINE=InnoDB;
INSERT INTO mvcc_demo VALUES (1,'Alice',100),(2,'Bob',100)
  ON DUPLICATE KEY UPDATE balance=VALUES(balance);

DROP PROCEDURE IF EXISTS flood;
DELIMITER //
-- 对 id=1 连做 n 次 UPDATE：每次产生一个 undo 旧版本（用于 ch05 purge / ch07 redo scenario）
CREATE PROCEDURE flood(n INT)
BEGIN
  DECLARE i INT DEFAULT 0;
  WHILE i < n DO
    UPDATE mvcc_demo SET balance = balance + 1 WHERE id = 1;
    SET i = i + 1;
  END WHILE;
END //
DELIMITER ;

-- ch06 锁 / ch08 调优：5 万行级演示表（city 有索引、age 无索引）
CREATE TABLE IF NOT EXISTS up2 (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL,
  age INT NOT NULL,
  city VARCHAR(64) NOT NULL,
  PRIMARY KEY(id),
  KEY idx_city (city)
) ENGINE=InnoDB;

DROP PROCEDURE IF EXISTS seed;
DELIMITER //
-- 灌 n 行到 up2（5 个城市均匀分布、age 1~90）。用法：CALL seed(50000);
CREATE PROCEDURE seed(n INT)
BEGIN
  DECLARE i INT DEFAULT 0;
  WHILE i < n DO
    INSERT INTO up2(name,age,city)
    VALUES (CONCAT('u',i), (i*7)%90+1, ELT((i%5)+1,'Taipei','Tokyo','Osaka','Kyoto','Nara'));
    SET i = i + 1;
  END WHILE;
END //
DELIMITER ;

DROP PROCEDURE IF EXISTS storm;
DELIMITER //
-- n 次全表 UPDATE：每次弄脏大量页 + 写约 4MB redo（ch11 写风暴 scenario）。
-- 先 CALL seed(50000) 灌满 up2 再用。多连接并发 CALL storm() 制造写压力。
CREATE PROCEDURE storm(n INT)
BEGIN
  DECLARE i INT DEFAULT 0;
  WHILE i < n DO
    UPDATE up2 SET age = age + 1;
    SET i = i + 1;
  END WHILE;
END //
DELIMITER ;
