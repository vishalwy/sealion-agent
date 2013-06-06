VERSION="-v"`cat ../build/version`
SERVER="192.168.1.70"
INSTALLER_HELPER_PATH=/var/www/sealion/webclient/overViewUI/downloads/
INSTALLER_PATH=/var/www/sealion/webclient/overViewUI/downloads/
UPDATE_PATH=/var/www/sealion/webclient/overViewUI/downloads/
UPDATE_HELPER_PATH=/var/www/sealion/webclient/overViewUI/downloads/
USER="vishal"
PWD="cameo15jay"

pscp -l $USER -pw $PWD sealion.sh $SERVER:$INSTALLER_HELPER_PATH
pscp -l $USER -pw $PWD r $SERVER:$INSTALLER_PATH
#pscp -l $USER -pw $PWD update.sh $SERVER:$UPDATE_PATH
