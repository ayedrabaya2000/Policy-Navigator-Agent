from handlers.vehicle_code_handler import VehicleCodeHandler
from handlers.epa_handler import EPAHandler
from handlers.federal_register_handler import FederalRegisterHandler
from handlers.courtlistener_handler import CourtListenerHandler
from handlers.document_upload_handler import UploadHandler
class PolicyNavigatorFacade:
    def __init__(self, slack_token=None, slack_channel=None):
        self.handlers = {
            'vehicle code': VehicleCodeHandler(),
            'epa': EPAHandler(),
            'federal register': FederalRegisterHandler(),
            'courtlistener': CourtListenerHandler(),
        }
        self.upload_handler = UploadHandler()
    def handle_query(self, query: str) -> str:
        prefix = query.split(':', 1)[0].strip().lower()
        handler = self.handlers.get(prefix)
        if handler:
            return handler.run(query)
        else:
            return "[Error] Unknown query type."
    def handle_upload(self, path_or_url: str) -> str:
        return self.upload_handler.ingest(path_or_url) 