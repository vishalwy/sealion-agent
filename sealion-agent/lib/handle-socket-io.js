/* 
This module handles socketIO
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var io = require('socket.io-client');
var logData = require('./log.js');
var socketIoOptions = require('../etc/config/server-config.json').socketIODetails;
var SealionGlobal = require('./global.js');
var executeServices = require('./execute-services.js');
var uninstallSelf = require('./uninstall-self.js');
var updateConfig = require('./update-config.js');
var updateAgent = require('./update-agent.js');
var agentDetails = require('../etc/config/agent-config.json');
var self;

/** @constructor */
function HandleSocketIO( ) {

    if(self) {
        self.closeConnection();
    }

    self = this;

    // variable to check if reconnect is required.
    // changed to false when socket is closed by the program
    this.reconnect = true;
};

// creates new socketIO connection
HandleSocketIO.prototype.createConnection = function() {
    var tempThis = this;

    if(! this.socket) {

        this.socket = io.connect(socketIoOptions.url);
        this.socket.on('connect', this.onConnect);
        this.socket.on('joined', this.onJoined);
        this.socket.on('left', this.onLeft);
        this.socket.on('agent_removed', this.onAgentRemoved);
        this.socket.on('server_category_changed', this.onServerCategoryChanged);
        this.socket.on('activitylist_in_category_updated', this.onActivityListUpdated);
        this.socket.on('activity_updated', this.onActivityUpdated);
        this.socket.on('upgrade_agent', this.onUpgradeAgent);
        this.socket.on('message', this.onMsg);
        this.socket.on('error', this.onError);
        this.socket.on('unhandledException', this.onUnhandledException);
        this.socket.on('disconnect', this.onDisconnect);
    } else {
        if(this.socket.socket.connected) {
            this.socket.socket.disconnectSync();
        }
        this.socket.socket.connect();
    }
}

// closes socketIO connection
HandleSocketIO.prototype.closeConnection = function( ) {

    this.reconnect = false;

    if(this.socket && this.socket.socket.connected) {
        this.socket.socket.disconnectSync();
    }
}

HandleSocketIO.prototype.onConnect = function () {

    logData("Socket IO connected");

    if(self) {
        self.socket.emit('join', { org : SealionGlobal.orgId });
        self.socket.emit('join', {
            org : SealionGlobal.orgId
            , category : SealionGlobal.categoryId
        });
    }

};

HandleSocketIO.prototype.onJoined = function (data) {
    if( data.category ) {
        logData('Joined category room');
    } else {
        logData('Joined organization room');
    }
};


HandleSocketIO.prototype.onLeft = function (data) {
    logData('SocketIO: Left category room');
}

HandleSocketIO.prototype.onAgentRemoved = function (data) {
    logData('SocketIO: Remove agent');
    if(data.servers.indexOf(SealionGlobal.agentId) >= 0) {
        executeServices.shutDown();
        uninstallSelf();
        process.nextTick( function() {
            process.exit(0);
        });
    }
}

HandleSocketIO.prototype.onServerCategoryChanged = function (data) {
    logData('SocketIO: Category change');
    if( self && data.servers.indexOf(SealionGlobal.agentId) >= 0 ) {
        logData('SocketIO: Changing category');

        self.socket.emit('leave', {
              org : SealionGlobal.orgId
            , category : SealionGlobal.categoryId
        });

        SealionGlobal.categoryId = data.category;

        self.socket.emit('join', {
              org : SealionGlobal.orgId
            , category : SealionGlobal.categoryId
        });

        updateConfig();
    }
}

HandleSocketIO.prototype.onActivityListUpdated = function (data) {
    logData('SocketIO: Update config');
    updateConfig();
}

HandleSocketIO.prototype.onActivityUpdated = function (data) {
    logData('SocketIO: Update config');
    updateConfig();
}

HandleSocketIO.prototype.onUpgradeAgent = function (data) {
    logData('SocketIO: updating to agent-version ' + data.agentVersion)

    if(data.agentVersion != agentDetails.agentVersion) {
        executeServices.shutDown();
        updateAgent(data.agentVersion);
        process.nextTick( function() {
            process.exit(0);
        });
    }
}


HandleSocketIO.prototype.onError = function(error) {
    logData("Error in Socket.io connection " + error);
}

HandleSocketIO.prototype.onUnhandledException = function(error) {
    logData('Socket.io Caught unhandled exception');
}

HandleSocketIO.prototype.onMsg = function(msg) {
    logData(msg);
}

HandleSocketIO.prototype.onDisconnect = function() {
    logData("Socket.io Connection disconnected");

    if(self.reconnect) {
        self.createConnection();
    }
}

module.exports = HandleSocketIO;
