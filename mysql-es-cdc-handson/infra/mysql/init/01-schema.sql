CREATE DATABASE IF NOT EXISTS product_catalog
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE product_catalog;

CREATE TABLE categories (
  id BIGINT NOT NULL,
  name VARCHAR(200) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE products (
  id BIGINT NOT NULL,
  sku VARCHAR(100) NOT NULL,
  name VARCHAR(200) NOT NULL,
  description TEXT NOT NULL,
  category_id BIGINT NOT NULL,
  price_cents BIGINT NOT NULL,
  status VARCHAR(32) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_products_sku (sku),
  KEY ix_products_category (category_id),
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id),
  CONSTRAINT ck_products_price CHECK (price_cents >= 0),
  CONSTRAINT ck_products_status CHECK (status IN ('ACTIVE', 'DELETED'))
) ENGINE=InnoDB;

CREATE TABLE inventory (
  product_id BIGINT NOT NULL,
  available_quantity INT NOT NULL,
  reserved_quantity INT NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (product_id),
  CONSTRAINT fk_inventory_product FOREIGN KEY (product_id) REFERENCES products(id),
  CONSTRAINT ck_inventory_available CHECK (available_quantity >= 0),
  CONSTRAINT ck_inventory_reserved CHECK (reserved_quantity >= 0)
) ENGINE=InnoDB;

CREATE TABLE product_search_revision (
  product_id BIGINT NOT NULL,
  revision BIGINT NOT NULL,
  active BOOLEAN NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (product_id),
  CONSTRAINT fk_revision_product FOREIGN KEY (product_id) REFERENCES products(id),
  CONSTRAINT ck_revision_positive CHECK (revision > 0)
) ENGINE=InnoDB;
