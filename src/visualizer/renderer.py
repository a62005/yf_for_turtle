from jinja2 import Environment, FileSystemLoader
import os

def render_stats_html(daily_processed: list, weekly_processed: list = None) -> str:
    """
    Renders processed stats into an HTML table grid using Jinja2.
    
    Args:
        daily_processed: List of daily category stats.
        weekly_processed: Optional list of weekly category stats.
        
    Returns:
        String containing the rendered HTML.
    """
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('stats_table.html')
    return template.render(daily=daily_processed, weekly=weekly_processed)
