var daemon = require('daemon');
var lockFile = require('./etc/config/lockfile.json').lockFile;
var authenticate = require('./lib/authentication.js').authenticate;
var fs = require('fs');

var args = process.argv;
var dPID;

switch(args[2]) {
    case "stop":
        process.kill(parseInt(fs.readFileSync(lockFile)));
        fs.unlinkSync(lockFile);
        process.exit(0);
    break;

    case "start":
        dPID = daemon.start('/tmp/sealion.log', '/tmp/sealion.err');
        daemon.lock(lockFile);
        fs.writeFileSync(lockFile, dPID.toString(), 'utf8');    
    break;

    default:
        console.log('Usage: [start|stop]');
        process.exit(0);
    break;
}

authenticate();
