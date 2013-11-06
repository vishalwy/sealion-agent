/* 
This module handles socketIO
*/

/*********************************************

 (c) Webyog, Inc.

*********************************************/

var io = require('socket.io-client');
var logData = require('./log.js');
var socketIoOptions = require('../etc/config/sealion-config.json').socketIODetails;
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

    if(this.socket && this.socket.socket && (this.socket.socket.connected || this.socket.socket.connecting)) {
        return;
    }

    if(SealionGlobal.http_proxy){
        this.socket = io.connect(socketIoOptions.url, {transports : ['xhr-polling']});
    } else {
        this.socket = io.connect(socketIoOptions.url);
    }

    if(this.socket) {
        this.reconnect = true;
        this.socket.removeListener('connect', this.onConnect);
        this.socket.removeListener('joined', this.onJoined);
        this.socket.removeListener('left', this.onLeft);
        this.socket.removeListener('agent_removed', this.onAgentRemoved);
        this.socket.removeListener('server_category_changed', this.onServerCategoryChanged);
        this.socket.removeListener('category_deleted', this.onCategoryDeleted);
        this.socket.removeListener('activity_deleted', this.onActivityDeleted);
        this.socket.removeListener('activitylist_in_category_updated', this.onActivityListUpdated);
        this.socket.removeListener('activity_updated',this.onActivityUpdated);
        this.socket.removeListener('upgrade_agent', this.onUpgradeAgent);
        this.socket.removeListener('org_token_resetted', this.onOrgTokenResetted);
        this.socket.removeListener('message', this.onMsg);
        this.socket.removeListener('error', this.onError);
        this.socket.removeListener('unhandledException', this.onUnhandledException);
        this.socket.removeListener('disconnect', this.onDisconnect);

        this.socket.on('connect', this.onConnect);
        this.socket.on('joined', this.onJoined);
        this.socket.on('left', this.onLeft);
        this.socket.on('agent_removed', this.onAgentRemoved);
        this.socket.on('server_category_changed', this.onServerCategoryChanged);
        this.socket.on('category_deleted', this.onCategoryDeleted);
        this.socket.on('activity_deleted', this.onActivityDeleted);
        this.socket.on('activitylist_in_category_updated', this.onActivityListUpdated);
        this.socket.on('activity_updated', this.onActivityUpdated);
        this.socket.on('upgrade_agent', this.onUpgradeAgent);
        this.socket.on('org_token_resetted', this.onOrgTokenResetted);
        this.socket.on('message', this.onMsg);
        this.socket.on('error', this.onError);
        this.socket.on('unhandledException', this.onUnhandledException);
        this.socket.on('disconnect', this.onDisconnect);
    }
}

HandleSocketIO.prototype.joinCatRoom = function() {
    if(self) {
        self.socket.emit('join', {
            org : SealionGlobal.orgId
            , category : SealionGlobal.categoryId
        });
    }
};

// closes socketIO connection
HandleSocketIO.prototype.closeConnection = function( ) {

    this.reconnect = false;

    if(this.socket && this.socket.socket.connected) {
        this.socket.socket.disconnect();
    }
};

HandleSocketIO.prototype.onConnect = function () {

    logData("SocketIO: Connected");

    if(self) {
        self.socket.emit('join', { org : SealionGlobal.orgId });
        self.socket.emit('join', {
            org : SealionGlobal.orgId
            , category : SealionGlobal.categoryId
        });
    }
};

HandleSocketIO.prototype.onJoined = function (data) {
    if( data && data.category ) {
        logData('SocketIO: Joined category room');
    } else {
        logData('SocketIO: Joined organization room');
    }
};


HandleSocketIO.prototype.onLeft = function (data) {
    logData('SocketIO: Left category room');
};

HandleSocketIO.prototype.onAgentRemoved = function (data) {
    logData('SocketIO: Remove agent');
    if(! data.servers || data.servers.indexOf(SealionGlobal.agentId) >= 0) {
        executeServices.shutDown();
        uninstallSelf();
        process.nextTick( function() {
            process.exit(0);
        });
    }
};

HandleSocketIO.prototype.onCategoryDeleted = function(data) {
    logData('SocketIO: Category Deleted');
    if(data && data.category && data.category === SealionGlobal.categoryId){
        logData('SocketIO: Fetching data for new category');
        updateConfig();
    }
};

HandleSocketIO.prototype.onActivityDeleted = function(data) {
    logData('SocketIO: Activity Deleted');

    if(data && data.activity && SealionGlobal.services[data.activity]) {
        logData('SocketIO: Update config');
        updateConfig();
    }
};

HandleSocketIO.prototype.onServerCategoryChanged = function (data) {
    logData('SocketIO: Category change');
    if( self && data && data.servers && data.servers.indexOf(SealionGlobal.agentId) >= 0 ) {
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
};

HandleSocketIO.prototype.onActivityListUpdated = function (data) {
    logData('SocketIO: Update config');
    updateConfig();
};

HandleSocketIO.prototype.onActivityUpdated = function (data) {
    logData('SocketIO: Update config');
    updateConfig();
};

HandleSocketIO.prototype.onOrgTokenResetted = function(data) {
    logData('SocketIO: Organization token resetted');
    executeServices.shutDown();
    process.nextTick( function() {
        process.exit(0);
    });
};

HandleSocketIO.prototype.onUpgradeAgent = function (data) {
    logData('SocketIO: Updating to agent-version ' + data.agentVersion)

    if(data.agentVersion != agentDetails.agentVersion) {
        executeServices.shutDown();
        updateAgent(data.agentVersion);
        process.nextTick( function() {
            process.exit(0);
        });
    }
}

HandleSocketIO.prototype.onError = function(error) {
    logData("SocketIO: Error in Socket.io connection " + error);
}

HandleSocketIO.prototype.onUnhandledException = function(error) {
    logData('SocketIO: Caught unhandled exception');
}

HandleSocketIO.prototype.onMsg = function(msg) {
    logData(msg);
}

HandleSocketIO.prototype.onDisconnect = function() {
    logData("SocketIO: Connection disconnected");

    if(self.reconnect) {
        self.createConnection();
    }
}

module.exports = HandleSocketIO;
