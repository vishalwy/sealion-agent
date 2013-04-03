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
};

module.exports = SealionGlobal;
