class SocketIONamespace(BaseNamespace):
    def on_connect(self):
        print '[Connected]'

    def on_activity_updated(self, *args):
        print '[activity_updated]'

    def on_activitylist_in_category_updated(self, *args):
        print '[activitylist_in_category_updated]'

    def on_agent_removed(self, *args):
        print '[agent_removed]'

    def on_org_token_resetted(self, *args):
        print '[org_token_resetted]'

    def on_server_category_changed(self, *args):
        print '[server_category_changed]'

    def on_activity_deleted(self, *args):
        print '[activity_deleted]'