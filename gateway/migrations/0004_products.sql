CREATE TABLE products (
 id TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 model TEXT NOT NULL DEFAULT '',
 daily_limit INTEGER NOT NULL CHECK(daily_limit BETWEEN 1 AND 100000),
 monthly_price INTEGER CHECK(monthly_price BETWEEN 0 AND 1000000000000),
 yearly_price INTEGER CHECK(yearly_price BETWEEN 0 AND 1000000000000),
 published INTEGER NOT NULL DEFAULT 0 CHECK(published IN (0,1)),
 position INTEGER NOT NULL,
 updated_at INTEGER NOT NULL DEFAULT 0
);
INSERT INTO products(id,title,description,daily_limit,position) VALUES
 ('basic','پایه','برای شروع کار با رصام',20,1),
 ('professional','حرفه‌ای','برای استفادهٔ روزمره و پرسش‌های بیشتر',100,2),
 ('business','سازمانی','برای تیم‌هایی با نیاز بیشتر',300,3);
CREATE TABLE product_changes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 product_id TEXT NOT NULL REFERENCES products(id),
 actor TEXT NOT NULL,
 created_at INTEGER NOT NULL,
 details TEXT NOT NULL
);
ALTER TABLE licenses ADD COLUMN model TEXT;
ALTER TABLE licenses ADD COLUMN product_id TEXT;
