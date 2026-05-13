-- Schema for hands-on scenarios. sbtest table mirrors sysbench-oltp shape
-- so we can load it with sysbench or hand-crafted INSERTs.

CREATE DATABASE IF NOT EXISTS sbtest
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE sbtest;

CREATE TABLE IF NOT EXISTS sbtest1 (
  id INT NOT NULL AUTO_INCREMENT,
  k  INT NOT NULL DEFAULT 0,
  c  CHAR(120) NOT NULL DEFAULT '',
  pad CHAR(60) NOT NULL DEFAULT '',
  PRIMARY KEY (id),
  KEY k_1 (k)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A second table without secondary index, used in scenarios that build
-- their own index to observe before/after.
CREATE TABLE IF NOT EXISTS user_profile (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL,
  age  INT NOT NULL,
  city VARCHAR(64) NOT NULL,
  email VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
