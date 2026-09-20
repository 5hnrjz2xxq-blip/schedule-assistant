import Foundation

/// Generates ICS calendar files from parsed courses
class ICSGenerator {
    
    // MARK: - Generate ICS Content
    
    /// Generate ICS content from parsed courses
    static func generateICS(from courses: [ParsedCourse]) -> String {
        var ics = "BEGIN:VCALENDAR\r\n"
        ics += "VERSION:2.0\r\n"
        ics += "PRODID:-//Yibin University//Schedule//EN\r\n"
        ics += "CALSCALE:GREGORIAN\r\n"
        ics += "METHOD:PUBLISH\r\n"
        ics += "X-WR-CALNAME:宜宾学院课程表\r\n"
        ics += "X-WR-TIMEZONE:Asia/Shanghai\r\n"
        
        // Add VTIMEZONE for Asia/Shanghai
        ics += "BEGIN:VTIMEZONE\r\n"
        ics += "TZID:Asia/Shanghai\r\n"
        ics += "BEGIN:STANDARD\r\n"
        ics += "DTSTART:19700101T000000\r\n"
        ics += "TZOFFSETFROM:+0800\r\n"
        ics += "TZOFFSETTO:+0800\r\n"
        ics += "TZNAME:CST\r\n"
        ics += "END:STANDARD\r\n"
        ics += "END:VTIMEZONE\r\n"
        
        // Generate events for each course
        for course in courses {
            let dates = ScheduleExtractor.generateDates(for: course)
            
            for (index, date) in dates.enumerated() {
                let event = createEvent(for: course, on: date, index: index)
                ics += event
            }
        }
        
        ics += "END:VCALENDAR\r\n"
        
        return ics
    }
    
    /// Create a single VEVENT for a course on a specific date
    static func createEvent(for course: ParsedCourse, on date: Date, index: Int) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd'T'HHmmss"
        formatter.timeZone = TimeZone(identifier: "Asia/Shanghai")
        
        // Parse start and end times
        let startTimeParts = course.startTime.components(separatedBy: ":")
        let endTimeParts = course.endTime.components(separatedBy: ":")
        
        let startHour = Int(startTimeParts[0]) ?? 8
        let startMinute = Int(startTimeParts[1]) ?? 20
        let endHour = Int(endTimeParts[0]) ?? 10
        let endMinute = Int(endTimeParts[1]) ?? 0
        
        // Create start and end dates
        var startComponents = Calendar.current.dateComponents([.year, .month, .day], from: date)
        startComponents.hour = startHour
        startComponents.minute = startMinute
        
        var endComponents = Calendar.current.dateComponents([.year, .month, .day], from: date)
        endComponents.hour = endHour
        endComponents.minute = endMinute
        
        guard let startDate = Calendar.current.date(from: startComponents),
              let endDate = Calendar.current.date(from: endComponents) else {
            return ""
        }
        
        // Generate UID
        let uid = "\(course.courseCode)-\(course.dayOfWeek)-\(index)-\(Int(date.timeIntervalSince1970))@yibinu.edu.cn"
        
        // Generate RRULE (not needed for individual events)
        // For recurring events, we'd use RRULE, but since we're generating individual events, we don't need it
        
        // Format dates
        let dtstart = formatter.string(from: startDate)
        let dtend = formatter.string(from: endDate)
        
        // Create DESCRIPTION
        let description = "教师: \(course.teacher)\\n时间: \(course.timeSlot)\\n周次: \(course.weekSpec)"
        
        // Create event
        var event = "BEGIN:VEVENT\r\n"
        event += "UID:\(uid)\r\n"
        event += "DTSTAMP:\(formatter.string(from: Date()))\r\n"
        event += "DTSTART;TZID=Asia/Shanghai:\(dtstart)\r\n"
        event += "DTEND;TZID=Asia/Shanghai:\(dtend)\r\n"
        event += "SUMMARY:\(course.courseName)\r\n"
        event += "LOCATION:\(course.location)\r\n"
        event += "DESCRIPTION:\(description)\r\n"
        event += "END:VEVENT\r\n"
        
        return event
    }
    
    // MARK: - Save ICS File
    
    /// Save ICS content to a file in the Documents directory
    static func saveICS(_ content: String, filename: String = "课程表.ics") -> URL? {
        let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let fileURL = documentsPath.appendingPathComponent(filename)
        
        do {
            try content.write(to: fileURL, atomically: true, encoding: .utf8)
            print("ICS file saved to: \(fileURL.path)")
            return fileURL
        } catch {
            print("Failed to save ICS file: \(error)")
            return nil
        }
    }
    
    // MARK: - Validate ICS Content
    
    /// Basic validation of ICS content
    static func validateICS(_ content: String) -> Bool {
        let hasCalendar = content.contains("BEGIN:VCALENDAR")
        let hasEndCalendar = content.contains("END:VCALENDAR")
        let hasEvents = content.contains("BEGIN:VEVENT")
        let hasTimezone = content.contains("VTIMEZONE")
        
        return hasCalendar && hasEndCalendar && hasEvents && hasTimezone
    }
}
