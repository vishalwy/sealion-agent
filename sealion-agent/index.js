/*********************************************

(c) Webyog, Inc.

*********************************************/

/*
Application starts with this page
*/

var lockFile = require('./etc/config/sealion-config.json').lockFile;
var logData = require('./lib/log.js');

var daemon = require('daemon');
var fs = require('fs');

var args = process.argv;
var dPID;

switch(args[2]) {
    case "stop":
        try {
            // Close the running instance
            process.kill(parseInt(fs.readFileSync(lockFile)));
            
            //delete lock file
            fs.unlinkSync(lockFile);
            process.exit(0);
        } catch (err) {
            logData('Failed to stop process. ' + err);
            process.exit(1);
        }
    break;

    case "start":
        // check if lock file exists, if yes then exit, as instance already running
        var exist = fs.existsSync(lockFile);
        if(exist){
            logData('Sealion service already running');
            process.exit(1);
        }

        /*
         Check if setuid function is present. Check is done so that process can be owned
         by user 'sealion'. This enables all functions be performed by user 'sealion'.
         In case of failure leave exit the program with error message
         */
        if (process.setuid) {
            try {
                process.setgid('sealion');
                process.setuid('sealion');
            } catch (err) {
                logData('Failed to set uid. ' + err);
                process.exit(1);
            }
        }

        try {
            // start the daemon
            dPID = daemon.start('var/log/sealion.log', 'var/log/sealion.err');
            daemon.lock(lockFile);
            fs.writeFileSync(lockFile, dPID.toString(), 'utf8');
        } catch(err) {
            logData('Failed to start service. ' + err);
            process.exit(1);
        }
    break;

    default:
        logData('Usage: [start|stop]');
        process.exit(0);
    break;
}

fs.chmod('/usr/local/sealion-agent/var/log/sealion.log', 644, function(err){
    if(err){
        logData('Unable to change permission of sealion.log');
    }
});

fs.chmod('/usr/local/sealion-agent/var/log/sealion.err', 644, function(err){
    if(err){
        logData('Unable to change permission of sealion.err');
    }
});

process.on('uncaughtException', function(err){
    var services = require('./lib/execute-services.js');
    var SealionGlobal = require('./lib/global.js');
    var objToSend = {};
    var agentConfig;

    objToSend.timestamp = Date.now();
    objToSend.stack = err.stack;

    var os = require('os');
    objToSend.os = {};
    objToSend.os.loadAvg = os.loadavg();
    objToSend.os.uptime = os.uptime();
    objToSend.os.freeMem = os.freemem();
    objToSend.os.totalMem = os.totalmem();
    objToSend.os.cpuCount = os.cpus().length;
    objToSend.os.platform = os.platform();
    objToSend.os.release = os.release();
    objToSend.os.arch = os.arch();

    objToSend.process = {};
    objToSend.process.pid = process.pid;
    objToSend.process.uid = process.getuid();
    objToSend.process.gid = process.getgid();
    objToSend.process.memoryUsage = process.memoryUsage();
    objToSend.process.isProxy =  SealionGlobal.http_proxy && SealionGlobal.http_proxy.length ? true : false;
    objToSend.process.uptime = process.uptime();

    var todayDate = new Date(objToSend.timestamp);
    //console.error(todayDate.toString() + ' ' + err.stack);


    services.saveCrashData(objToSend, function(){
        require('./lib/restart-agent.js')();
        process.exit(1);
    });
});

var authenticate = require('./lib/authentication.js').authenticate;
var shutDown = require('./lib/execute-services.js').shutDown;

process.title = 'sealion-node';

// Handle message SIGTERM
process.on('SIGTERM', function() {
    shutDown();
    logData('SIGTERM: services closed');
    process.exit(0);        
});

// Handle message SIGINT
process.on('SIGINT', function() {
    shutDown();
    logData('SIGINT: services closed');        
    process.exit(0);
});

logData('Sealion-Agent: service started');

// After initial file setups and starting daemon check for authentication
authenticate();