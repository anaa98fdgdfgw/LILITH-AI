"""MCP Time Server for date, time, and timezone operations."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_server import BaseMCPServer, create_argument_parser
from datetime import datetime, timedelta, timezone
import time
from typing import Dict, Any, List, Optional
import calendar
import zoneinfo


class TimeServer(BaseMCPServer):
    """Time and date operations server."""
    
    def __init__(self, port: int = 3009):
        super().__init__("time", port)
        
        # Register methods
        self.register_method("get_current_time", self.get_current_time)
        self.register_method("get_current_date", self.get_current_date)
        self.register_method("get_timestamp", self.get_timestamp)
        self.register_method("format_time", self.format_time)
        self.register_method("parse_time", self.parse_time)
        self.register_method("add_time", self.add_time)
        self.register_method("time_difference", self.time_difference)
        self.register_method("convert_timezone", self.convert_timezone)
        self.register_method("get_timezone_info", self.get_timezone_info)
        self.register_method("list_timezones", self.list_timezones)
        self.register_method("get_calendar", self.get_calendar)
        self.register_method("is_weekend", self.is_weekend)
        self.register_method("is_holiday", self.is_holiday)
        self.register_method("set_timer", self.set_timer)
        self.register_method("get_week_info", self.get_week_info)
        
    async def get_current_time(self, timezone_name: str = None, format: str = "%Y-%m-%d %H:%M:%S") -> Dict[str, Any]:
        """Get current time."""
        try:
            if timezone_name:
                tz = zoneinfo.ZoneInfo(timezone_name)
                now = datetime.now(tz)
            else:
                now = datetime.now()
                
            return {
                "time": now.strftime(format),
                "iso": now.isoformat(),
                "timestamp": now.timestamp(),
                "timezone": str(now.tzinfo) if now.tzinfo else "local"
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_current_date(self, timezone_name: str = None, format: str = "%Y-%m-%d") -> Dict[str, Any]:
        """Get current date."""
        try:
            if timezone_name:
                tz = zoneinfo.ZoneInfo(timezone_name)
                today = datetime.now(tz).date()
            else:
                today = datetime.now().date()
                
            return {
                "date": today.strftime(format),
                "year": today.year,
                "month": today.month,
                "day": today.day,
                "weekday": today.strftime("%A"),
                "week_number": today.isocalendar()[1]
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_timestamp(self, milliseconds: bool = False) -> Dict[str, Any]:
        """Get current Unix timestamp."""
        try:
            ts = time.time()
            if milliseconds:
                ts = int(ts * 1000)
            else:
                ts = int(ts)
                
            return {"timestamp": ts, "milliseconds": milliseconds}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def format_time(self, timestamp: float = None, datetime_str: str = None, 
                         input_format: str = None, output_format: str = "%Y-%m-%d %H:%M:%S") -> Dict[str, Any]:
        """Format time/date."""
        try:
            if timestamp is not None:
                dt = datetime.fromtimestamp(timestamp)
            elif datetime_str is not None:
                if input_format:
                    dt = datetime.strptime(datetime_str, input_format)
                else:
                    dt = datetime.fromisoformat(datetime_str)
            else:
                dt = datetime.now()
                
            return {
                "formatted": dt.strftime(output_format),
                "iso": dt.isoformat(),
                "timestamp": dt.timestamp()
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def parse_time(self, time_str: str, format: str = None) -> Dict[str, Any]:
        """Parse time string."""
        try:
            if format:
                dt = datetime.strptime(time_str, format)
            else:
                # Try common formats
                formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                    "%Y/%m/%d",
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S.%f"
                ]
                
                dt = None
                for fmt in formats:
                    try:
                        dt = datetime.strptime(time_str, fmt)
                        break
                    except ValueError:
                        continue
                        
                if dt is None:
                    # Try ISO format
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    
            return {
                "year": dt.year,
                "month": dt.month,
                "day": dt.day,
                "hour": dt.hour,
                "minute": dt.minute,
                "second": dt.second,
                "weekday": dt.strftime("%A"),
                "timestamp": dt.timestamp(),
                "iso": dt.isoformat()
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def add_time(self, base_time: str = None, days: int = 0, hours: int = 0, 
                      minutes: int = 0, seconds: int = 0, weeks: int = 0) -> Dict[str, Any]:
        """Add time to a date."""
        try:
            if base_time:
                dt = datetime.fromisoformat(base_time.replace('Z', '+00:00'))
            else:
                dt = datetime.now()
                
            delta = timedelta(days=days, hours=hours, minutes=minutes, 
                            seconds=seconds, weeks=weeks)
            new_dt = dt + delta
            
            return {
                "original": dt.isoformat(),
                "new": new_dt.isoformat(),
                "delta": str(delta),
                "timestamp": new_dt.timestamp()
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def time_difference(self, time1: str, time2: str = None, unit: str = "seconds") -> Dict[str, Any]:
        """Calculate time difference."""
        try:
            dt1 = datetime.fromisoformat(time1.replace('Z', '+00:00'))
            
            if time2:
                dt2 = datetime.fromisoformat(time2.replace('Z', '+00:00'))
            else:
                dt2 = datetime.now()
                
            diff = dt2 - dt1
            total_seconds = diff.total_seconds()
            
            units = {
                "seconds": total_seconds,
                "minutes": total_seconds / 60,
                "hours": total_seconds / 3600,
                "days": total_seconds / 86400,
                "weeks": total_seconds / 604800
            }
            
            return {
                "difference": units.get(unit, total_seconds),
                "unit": unit,
                "human_readable": str(diff),
                "is_past": total_seconds < 0
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def convert_timezone(self, time_str: str, from_tz: str = None, to_tz: str = "UTC") -> Dict[str, Any]:
        """Convert time between timezones."""
        try:
            # Parse the time
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
            # If no timezone info, assume from_tz
            if dt.tzinfo is None and from_tz:
                from_zone = zoneinfo.ZoneInfo(from_tz)
                dt = dt.replace(tzinfo=from_zone)
            elif dt.tzinfo is None:
                # Assume local time
                dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                
            # Convert to target timezone
            to_zone = zoneinfo.ZoneInfo(to_tz)
            converted = dt.astimezone(to_zone)
            
            return {
                "original": dt.isoformat(),
                "converted": converted.isoformat(),
                "from_timezone": str(dt.tzinfo),
                "to_timezone": to_tz,
                "offset_change": (converted.utcoffset() - dt.utcoffset()).total_seconds() / 3600
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_timezone_info(self, timezone_name: str) -> Dict[str, Any]:
        """Get timezone information."""
        try:
            tz = zoneinfo.ZoneInfo(timezone_name)
            now = datetime.now(tz)
            
            return {
                "name": timezone_name,
                "current_time": now.isoformat(),
                "utc_offset": now.strftime("%z"),
                "utc_offset_hours": now.utcoffset().total_seconds() / 3600,
                "is_dst": bool(now.dst()),
                "dst_offset": now.dst().total_seconds() / 3600 if now.dst() else 0
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def list_timezones(self, filter: str = None) -> Dict[str, Any]:
        """List available timezones."""
        try:
            all_zones = sorted(zoneinfo.available_timezones())
            
            if filter:
                zones = [z for z in all_zones if filter.lower() in z.lower()]
            else:
                zones = all_zones
                
            # Get current time in major timezones
            major_zones = {}
            for zone_name in ["UTC", "US/Eastern", "US/Pacific", "Europe/London", 
                            "Europe/Paris", "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney"]:
                if zone_name in all_zones:
                    tz = zoneinfo.ZoneInfo(zone_name)
                    major_zones[zone_name] = datetime.now(tz).strftime("%H:%M")
                    
            return {
                "timezones": zones,
                "count": len(zones),
                "major_zones_current_time": major_zones
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_calendar(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """Get calendar for a month."""
        try:
            now = datetime.now()
            year = year or now.year
            month = month or now.month
            
            cal = calendar.monthcalendar(year, month)
            month_name = calendar.month_name[month]
            
            # Get month info
            first_day = datetime(year, month, 1)
            if month == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)
                
            return {
                "year": year,
                "month": month,
                "month_name": month_name,
                "calendar": cal,
                "first_day": first_day.strftime("%A"),
                "last_day": last_day.day,
                "weeks": len(cal)
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def is_weekend(self, date_str: str = None) -> Dict[str, Any]:
        """Check if date is weekend."""
        try:
            if date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                dt = datetime.now()
                
            is_weekend = dt.weekday() >= 5  # Saturday = 5, Sunday = 6
            
            return {
                "date": dt.date().isoformat(),
                "weekday": dt.strftime("%A"),
                "is_weekend": is_weekend,
                "is_weekday": not is_weekend
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def is_holiday(self, date_str: str = None, country: str = "US") -> Dict[str, Any]:
        """Check if date is a holiday (basic implementation)."""
        try:
            if date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                dt = datetime.now()
                
            # Basic US holidays (would need a proper holiday library for full support)
            us_holidays = {
                (1, 1): "New Year's Day",
                (7, 4): "Independence Day",
                (12, 25): "Christmas Day",
                (12, 31): "New Year's Eve"
            }
            
            # Check if it's a holiday
            date_tuple = (dt.month, dt.day)
            is_holiday = date_tuple in us_holidays
            holiday_name = us_holidays.get(date_tuple, None)
            
            return {
                "date": dt.date().isoformat(),
                "is_holiday": is_holiday,
                "holiday_name": holiday_name,
                "country": country,
                "note": "Basic holiday detection - only major fixed-date holidays"
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def set_timer(self, seconds: int, name: str = None) -> Dict[str, Any]:
        """Set a timer (returns immediately with timer info)."""
        try:
            timer_id = f"timer_{int(time.time() * 1000)}"
            end_time = datetime.now() + timedelta(seconds=seconds)
            
            return {
                "timer_id": timer_id,
                "name": name or timer_id,
                "duration_seconds": seconds,
                "start_time": datetime.now().isoformat(),
                "end_time": end_time.isoformat(),
                "note": "Timer info returned - actual timing must be handled by client"
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_week_info(self, date_str: str = None) -> Dict[str, Any]:
        """Get week information."""
        try:
            if date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                dt = datetime.now()
                
            # Get week info
            week_num = dt.isocalendar()[1]
            year = dt.isocalendar()[0]
            
            # Get start and end of week (Monday to Sunday)
            start_of_week = dt - timedelta(days=dt.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            
            # Get all days in the week
            week_days = []
            for i in range(7):
                day = start_of_week + timedelta(days=i)
                week_days.append({
                    "date": day.date().isoformat(),
                    "weekday": day.strftime("%A"),
                    "is_today": day.date() == datetime.now().date()
                })
                
            return {
                "week_number": week_num,
                "year": year,
                "start_date": start_of_week.date().isoformat(),
                "end_date": end_of_week.date().isoformat(),
                "current_day": dt.strftime("%A"),
                "days": week_days
            }
            
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    parser = create_argument_parser("MCP Time Server")
    args = parser.parse_args()
    
    server = TimeServer(port=args.port)
    server.run()