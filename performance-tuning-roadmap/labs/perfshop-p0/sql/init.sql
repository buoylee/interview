CREATE TABLE IF NOT EXISTS products (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(200) NOT NULL,
  category VARCHAR(50) NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_category (category)
) ENGINE=InnoDB;

DELIMITER //
CREATE PROCEDURE seed_products()
BEGIN
  DECLARE i INT DEFAULT 1;
  WHILE i <= 20000 DO
    INSERT INTO products (name, category, price, stock, description)
    VALUES (
      CONCAT('Product-', i),
      ELT(FLOOR(RAND() * 5) + 1, 'electronics', 'books', 'food', 'sports', 'clothing'),
      ROUND(RAND() * 1000 + 1, 2),
      FLOOR(RAND() * 500),
      CONCAT('Searchable product description number ', i, ' with keyword ', ELT(FLOOR(RAND() * 4) + 1, 'alpha', 'beta', 'gamma', 'delta'))
    );
    SET i = i + 1;
  END WHILE;
END //
DELIMITER ;

CALL seed_products();
DROP PROCEDURE seed_products;

