/*
Module contains global objects that are to be shared amongst modules
*/

/*********************************************

Author: Shubhansh <shubhansh.varshney@webyog.com>

*********************************************/

var SealionGlobal = {
      request : { } // request object
    , services : [ ] // array of objects of activities currently running
    , interId : [ ] // associative array of interval ids for the activities running
    , sessionCookie : '' // session cookie to be shared amongst socketIO and request
    , agentId : '' //agent ID is to be stored required for joining rooms for Socket.IO
    , orgId : '' // org ID is to be stored required for joining rooms for Socket.IO
    , categoryId : '' //category ID is to be stored required for joining category rooms for Socket.IO
};

module.exports = SealionGlobal;
