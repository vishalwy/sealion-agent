var io = require('socket.io-client');

var socket = io.connect('http://localhost:8000');

socket.on('connect', function() {
    console.log("connected");
});

socket.on('update', function(msg) {
    console.log('Got message ' + JSON.stringify(msg));
});

socket.on('error', function(error) {
    console.log("Error in connection");
});
