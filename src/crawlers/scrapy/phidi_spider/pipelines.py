"""Custom Scrapy pipelines for Phidi crawler."""
import json
from pathlib import Path


class JsonLinesExportPipeline:
    """
    Export items to NDJSON format (newline-delimited JSON).
    Maintains compatibility with existing Python/Node crawler output format.
    """
    
    def __init__(self):
        self.file = None
        self.output_path = None
    
    def open_spider(self, spider):
        """Open output file when spider starts."""
        # Get output path from spider settings
        self.output_path = getattr(spider, 'output_path', None)
        
        if self.output_path:
            output_file = Path(self.output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            self.file = output_file.open('w', encoding='utf-8')
    
    def close_spider(self, spider):
        """Close output file when spider finishes."""
        if self.file:
            self.file.close()
    
    def process_item(self, item, spider):
        """Write each item as a JSON line."""
        if self.file:
            line = json.dumps(dict(item), ensure_ascii=False) + '\n'
            self.file.write(line)
        return item
