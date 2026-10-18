// Uruchamiany przez obraz mongo TYLKO przy pierwszym starcie (pusty wolumen /data/db).
// Użytkownika root tworzą zmienne MONGO_INITDB_ROOT_*, tu tylko przygotowujemy bazę.
db = db.getSiblingDB("todos");
db.createCollection("todos");
