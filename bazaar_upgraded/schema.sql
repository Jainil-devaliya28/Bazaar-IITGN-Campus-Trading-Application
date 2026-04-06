-- ============================================================
-- CampusTrade – MySQL Schema
-- Run this in your MySQL client to create the database.
-- Flask-SQLAlchemy will also auto-create tables via db.create_all()
-- ============================================================

CREATE DATABASE IF NOT EXISTS bazaar_iitgn
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE bazaar_iitgn;

-- ─────────────────────────────────────────────
-- Members (base user record)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Members (
  member_id   INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(100)  NOT NULL,
  email       VARCHAR(150)  NOT NULL UNIQUE,
  phone       VARCHAR(20),
  created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  role        VARCHAR(20)   NOT NULL DEFAULT 'user'
);

-- ─────────────────────────────────────────────
-- Students (academic detail)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Students (
  student_id   INT AUTO_INCREMENT PRIMARY KEY,
  member_id    INT NOT NULL UNIQUE,
  college_name VARCHAR(200),
  department   VARCHAR(100),
  year         INT,
  roll_number  VARCHAR(50),
  CONSTRAINT fk_students_member
    FOREIGN KEY (member_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- Authentication
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Authentication (
  auth_id       INT AUTO_INCREMENT PRIMARY KEY,
  member_id     INT NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  last_login    DATETIME,
  CONSTRAINT fk_auth_member
    FOREIGN KEY (member_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- Products
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Products (
  product_id   INT AUTO_INCREMENT PRIMARY KEY,
  seller_id    INT NOT NULL,
  title        VARCHAR(200) NOT NULL,
  description  TEXT,
  price        DECIMAL(10,2) NOT NULL,
  category     VARCHAR(100),
  `condition`  VARCHAR(50),
  is_available TINYINT(1) NOT NULL DEFAULT 1,
  image_url    VARCHAR(500),
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_products_seller
    FOREIGN KEY (seller_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- TransactionHistory
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS TransactionHistory (
  txn_id     INT AUTO_INCREMENT PRIMARY KEY,
  product_id INT,
  buyer_id   INT NOT NULL,
  seller_id  INT NOT NULL,
  amount     DECIMAL(10,2) NOT NULL,
  status     VARCHAR(50) NOT NULL DEFAULT 'pending',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_txn_product
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
    ON DELETE SET NULL,
  CONSTRAINT fk_txn_buyer
    FOREIGN KEY (buyer_id) REFERENCES Members(member_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_txn_seller
    FOREIGN KEY (seller_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- Reviews
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Reviews (
  review_id   INT AUTO_INCREMENT PRIMARY KEY,
  product_id  INT NOT NULL,
  reviewer_id INT NOT NULL,
  reviewed_id INT NOT NULL,
  rating      INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment     TEXT,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_reviews_product
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_reviews_reviewer
    FOREIGN KEY (reviewer_id) REFERENCES Members(member_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_reviews_reviewed
    FOREIGN KEY (reviewed_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- Bargaining_Proposals
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Bargaining_Proposals (
  proposal_id    INT AUTO_INCREMENT PRIMARY KEY,
  product_id     INT NOT NULL,
  buyer_id       INT NOT NULL,
  proposed_price DECIMAL(10,2) NOT NULL,
  message        TEXT,
  status         VARCHAR(50) NOT NULL DEFAULT 'pending',
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_prop_product
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_prop_buyer
    FOREIGN KEY (buyer_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- Demands
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Demands (
  demand_id   INT AUTO_INCREMENT PRIMARY KEY,
  member_id   INT NOT NULL,
  title       VARCHAR(200) NOT NULL,
  description TEXT,
  category    VARCHAR(100),
  budget      DECIMAL(10,2),
  status      VARCHAR(50) NOT NULL DEFAULT 'open',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_demands_member
    FOREIGN KEY (member_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- Chat
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Chat (
  chat_id     INT AUTO_INCREMENT PRIMARY KEY,
  sender_id   INT NOT NULL,
  receiver_id INT NOT NULL,
  message     TEXT NOT NULL,
  is_read     TINYINT(1) NOT NULL DEFAULT 0,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_chat_sender
    FOREIGN KEY (sender_id) REFERENCES Members(member_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_chat_receiver
    FOREIGN KEY (receiver_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- Logs
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Logs (
  log_id      INT AUTO_INCREMENT PRIMARY KEY,
  member_id   INT,
  action_type VARCHAR(50) NOT NULL,
  description TEXT,
  `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_logs_member
    FOREIGN KEY (member_id) REFERENCES Members(member_id)
    ON DELETE SET NULL
);

-- ─────────────────────────────────────────────
-- Feedbacks
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Feedbacks (
  feedback_id INT AUTO_INCREMENT PRIMARY KEY,
  member_id   INT NOT NULL,
  subject     VARCHAR(200),
  message     TEXT NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_feedbacks_member
    FOREIGN KEY (member_id) REFERENCES Members(member_id)
    ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- Sample admin user (password: admin123)
-- Run AFTER Flask has created tables OR run manually.
-- bcrypt hash for "admin123" generated with Flask-Bcrypt
-- ─────────────────────────────────────────────
-- INSERT INTO Members (name, email, phone, role)
--   VALUES ('Admin User', 'admin@campustrade.com', '0000000000', 'admin');
-- INSERT INTO Students (member_id, college_name) VALUES (LAST_INSERT_ID(), 'CampusTrade HQ');
-- INSERT INTO Authentication (member_id, password_hash)
--   VALUES (LAST_INSERT_ID(), '$2b$12$REPLACE_WITH_ACTUAL_BCRYPT_HASH');
-- Use the seed_admin.py script instead (generates correct hash automatically).
