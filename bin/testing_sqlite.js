var sqlite3 = require('sqlite3');

var db = new sqlite3.Database('../etc/dbs/RepositoryDB.db');
db.serialize(function() {
    db.run('delete from repository');

    db.all('SELECT * FROM repository LIMIT 0,1', function(error, rows) {
        console.log(rows.length);
    });
});

db.close();

