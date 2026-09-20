"""
Python wrapper for the Node.js Playwright scraper
Calls scraper.mjs via subprocess and returns course data
"""

import subprocess
import json
import os
import sys

class PlaywrightScraper:
    """Wrapper for Node.js Playwright-based course scraper"""
    
    def __init__(self):
        # Path to the Node.js scraper
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.scraper_path = os.path.join(self.script_dir, 'scraper.mjs')
        
        # Verify scraper exists
        if not os.path.exists(self.scraper_path):
            raise FileNotFoundError(f"Scraper not found at {self.scraper_path}")
    
    def scrape_courses(self, username: str, password: str) -> list:
        """
        Scrape course schedule from Yibin University
        
        Args:
            username: Student ID
            password: Password
            
        Returns:
            List of course dictionaries with fields:
                - course_name: Course name
                - teacher: Teacher name
                - location: Classroom location
                - day_of_week: Day of week (1-7)
                - time_slot: Time slot (e.g., '3-4')
                - week_start: Starting week number
                - week_end: Ending week number
                - week_type: Week type ('单'/'双'/'')
                - course_code: Course code
        """
        try:
            # Run the Node.js scraper
            result = subprocess.run(
                ['node', self.scraper_path, username, password],
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                cwd=self.script_dir
            )
            
            if result.returncode != 0:
                raise Exception(f"Scraper failed: {result.stderr}")
            
            # Parse the JSON output
            # The scraper prints "Courses: [...]" as its final output
            output = result.stdout.strip()
            
            # Find the JSON array in the output
            json_start = output.find('[')
            json_end = output.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                raise Exception(f"Could not parse scraper output: {output}")
            
            json_str = output[json_start:json_end]
            courses = json.loads(json_str)
            
            return courses
            
        except subprocess.TimeoutExpired:
            raise Exception("Scraper timed out after 120 seconds")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse scraper output: {e}")
        except Exception as e:
            raise Exception(f"Scraper error: {str(e)}")


def scrape_courses(username: str, password: str) -> list:
    """
    Convenience function to scrape courses
    
    Args:
        username: Student ID
        password: Password
        
    Returns:
        List of course dictionaries
    """
    scraper = PlaywrightScraper()
    return scraper.scrape_courses(username, password)


# For testing
if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <username> <password>")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    try:
        courses = scrape_courses(username, password)
        print(f"Found {len(courses)} courses:")
        for course in courses:
            print(f"  - {course.get('course_name', 'Unknown')} ({course.get('teacher', 'Unknown')})")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
