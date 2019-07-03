mysql -uroot -e "CREATE USER 'relstoragetest'@'localhost' IDENTIFIED BY 'relstoragetest';"
mysql -uroot -e "CREATE DATABASE relstoragetest;"
mysql -uroot -e "GRANT ALL ON relstoragetest.* TO 'relstoragetest'@'localhost';"
mysql -uroot -e "CREATE DATABASE relstoragetest2;"
mysql -uroot -e "GRANT ALL ON relstoragetest2.* TO 'relstoragetest'@'localhost';"
mysql -uroot -e "CREATE DATABASE relstoragetest_hf;"
mysql -uroot -e "GRANT ALL ON relstoragetest_hf.* TO 'relstoragetest'@'localhost';"
mysql -uroot -e "CREATE DATABASE relstoragetest2_hf;"
mysql -uroot -e "GRANT ALL ON relstoragetest2_hf.* TO 'relstoragetest'@'localhost';"
mysql -uroot -e "GRANT SELECT ON performance_schema.* TO 'relstoragetest'@'localhost';"
mysql -uroot -e "FLUSH PRIVILEGES;"
