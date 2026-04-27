use agridb;
SELECT * FROM orders;
describe blockchain_ledger;
repair table users;
select user_id, name, role FROM users;
alter table users add column farm_size VARCHAR(50);
enum('pending','paid') default 'pending';
delete from orders where order_id = 25;
update orders SET order_id = '12' where order_id = '27';
INSERT INTO products (user_id, name, email, password, role, phone, address)
VALUES
(4, 'Priya Ghosh', 'priya@organic.com', 'priya123', 'Buyer', '9283728293','Kolkata, Bengal');



