import Foundation

/// Handles parsing of raw course data extracted from the web page
class ScheduleExtractor {
    
    // MARK: - Semester Configuration
    static let semesterStartDate = Calendar.current.date(from: DateComponents(year: 2026, month: 3, day: 2))!
    static let calendar = Calendar(identifier: .gregorian)
    
    // MARK: - Parse Raw Course Entries
    
    /// Parse raw course entries into structured ParsedCourse objects
    static func parseCourses(from entries: [RawCourseEntry]) -> [ParsedCourse] {
        var parsedCourses: [ParsedCourse] = []
        
        for entry in entries {
            if let parsed = parseSingleCourse(from: entry) {
                parsedCourses.append(parsed)
            }
        }
        
        return parsedCourses
    }
    
    /// Parse a single raw course entry
    static func parseSingleCourse(from entry: RawCourseEntry) -> ParsedCourse? {
        let text = entry.full
        
        // Extract course code and name
        // Format: "N24ZYDZ082 EDA技术及应用[06]"
        let courseCodeNamePattern = "^([A-Z0-9]+)\\s+(.+?)\\[\\d+\\]"
        guard let codeNameMatch = text.range(of: courseCodeNamePattern, options: .regularExpression) else {
            print("Failed to parse course code/name from: \(text)")
            return nil
        }
        
        let matchedText = String(text[codeNameMatch])
        let parts = matchedText.components(separatedBy: " ")
        let courseCode = parts.first ?? ""
        let courseNameFull = parts.dropFirst().joined(separator: " ")
        let courseName = courseNameFull.replacingOccurrences(of: "[0-9]+]$", with: "", options: .regularExpression).trimmingCharacters(in: .whitespaces)
        
        // Extract teacher name (after [] and before schedule info)
        // Format: "[06]       李嘉勋       2-3周"
        let teacherPattern = "\\]\\s+(.+?)\\s+\\d"
        let teacher: String
        if let teacherMatch = text.range(of: teacherPattern, options: .regularExpression) {
            teacher = String(text[teacherMatch])
                .replacingOccurrences(of: "]", with: "")
                .replacingOccurrences(of: "^\\s+", with: "", options: .regularExpression)
                .replacingOccurrences(of: "\\s+\\d$", with: "", options: .regularExpression)
                .trimmingCharacters(in: .whitespaces)
        } else {
            teacher = "Unknown"
        }
        
        // Extract location (last part after time slot)
        // Format: "...1-2节,临港校区八号楼409"
        let locationPattern = "节,([^,]+)$"
        let location: String
        if let locationMatch = text.range(of: locationPattern, options: .regularExpression) {
            location = String(text[locationMatch])
                .replacingOccurrences(of: "节,", with: "")
                .trimmingCharacters(in: .whitespaces)
        } else {
            location = "Unknown"
        }
        
        // Extract day of week (星期1-5)
        let dayPattern = "星期(\\d)"
        let dayOfWeek: Int
        if let dayMatch = text.range(of: dayPattern, options: .regularExpression) {
            let dayStr = String(text[dayMatch]).replacingOccurrences(of: "星期", with: "")
            dayOfWeek = Int(dayStr) ?? 0
        } else {
            dayOfWeek = 0
        }
        
        // Extract time slot (1-2节, 3-4节, 5-8节)
        let timeSlotPattern = "(\\d-\\d+节)"
        let timeSlot: String
        if let slotMatch = text.range(of: timeSlotPattern, options: .regularExpression) {
            timeSlot = String(text[slotMatch])
        } else {
            timeSlot = "1-2节"
        }
        
        // Extract week specification
        // Format: "2-3周,5-17周(单)" or "2-18周(双)"
        let weekSpecPattern = "(\\d+-\\d+周(?:\\([单双]\\))?(?:,\\d+-\\d+周(?:\\([单双]\\))?)*)"
        let weekSpec: String
        if let weekMatch = text.range(of: weekSpecPattern, options: .regularExpression) {
            weekSpec = String(text[weekMatch])
        } else {
            weekSpec = "1-16周"
        }
        
        // Parse week ranges
        let weekRanges = parseWeekRanges(from: weekSpec)
        
        // Handle multi-slot courses (5-8节 = 5-6节 + 7-8节)
        let slots: [(String, String, String)]
        if timeSlot == "5-8节" {
            slots = [
                ("5-6节", "14:30", "16:05"),
                ("7-8节", "16:25", "18:00")
            ]
        } else if let slotTime = TimeSlot.time(for: timeSlot) {
            slots = [
                (timeSlot, 
                 String(format: "%02d:%02d", slotTime.startHour, slotTime.startMinute),
                 String(format: "%02d:%02d", slotTime.endHour, slotTime.endMinute))
            ]
        } else {
            slots = [(timeSlot, "08:30", "10:05")]
        }
        
        // Return first slot (for now, we'll create multiple entries for multi-slot)
        if let firstSlot = slots.first {
            return ParsedCourse(
                courseCode: courseCode,
                courseName: courseName,
                teacher: teacher,
                location: location,
                dayOfWeek: dayOfWeek,
                timeSlot: firstSlot.0,
                startTime: firstSlot.1,
                endTime: firstSlot.2,
                weekSpec: weekSpec,
                weekRanges: weekRanges
            )
        }
        
        return nil
    }
    
    /// Parse week specification string into WeekRange array
    static func parseWeekRanges(from spec: String) -> [WeekRange] {
        var ranges: [WeekRange] = []
        
        // Split by comma to handle multiple ranges
        let components = spec.components(separatedBy: ",")
        
        for component in components {
            let trimmed = component.trimmingCharacters(in: .whitespaces)
            
            // Pattern: "2-3周" or "5-17周(单)" or "2-18周(双)"
            let rangePattern = "(\\d+)-(\\d+)周(?:\\(([单双])\\))?"
            
            if let match = trimmed.range(of: rangePattern, options: .regularExpression) {
                let matchStr = String(trimmed[match])
                
                // Extract start and end weeks
                let startEndPattern = "(\\d+)-(\\d+)"
                if let startEndMatch = matchStr.range(of: startEndPattern, options: .regularExpression) {
                    let startEndStr = String(matchStr[startEndMatch])
                    let parts = startEndStr.components(separatedBy: "-")
                    
                    if let start = Int(parts[0]), let end = Int(parts[1]) {
                        // Check for odd/even modifier
                        var isOdd: Bool? = nil
                        var isEven: Bool? = nil
                        
                        if matchStr.contains("(单)") {
                            isOdd = true
                        } else if matchStr.contains("(双)") {
                            isEven = true
                        }
                        
                        ranges.append(WeekRange(startWeek: start, endWeek: end, isOddWeeks: isOdd, isEvenWeeks: isEven))
                    }
                }
            }
        }
        
        return ranges.isEmpty ? [WeekRange(startWeek: 1, endWeek: 16, isOddWeeks: nil, isEvenWeeks: nil)] : ranges
    }
    
    // MARK: - Generate Calendar Dates
    
    /// Generate all dates for a course based on week ranges
    static func generateDates(for course: ParsedCourse) -> [Date] {
        var dates: [Date] = []
        
        for weekRange in course.weekRanges {
            for week in weekRange.startWeek...weekRange.endWeek {
                // Skip if odd/even filter doesn't match
                if let isOdd = weekRange.isOddWeeks, isOdd && week % 2 == 0 {
                    continue
                }
                if let isEven = weekRange.isEvenWeeks, isEven && week % 2 != 0 {
                    continue
                }
                
                // Calculate date for this week
                if let date = dateForWeek(week, dayOfWeek: course.dayOfWeek) {
                    dates.append(date)
                }
            }
        }
        
        return dates
    }
    
    /// Get the date for a specific week and day of week
    static func dateForWeek(_ week: Int, dayOfWeek: Int) -> Date? {
        // Semester starts on Monday, week 1
        // Day 1 = Monday, Day 2 = Tuesday, etc.
        let startWeek = 1
        let weekOffset = week - startWeek
        
        // Calculate the date
        var dateComponents = DateComponents()
        dateComponents.year = 2026
        dateComponents.month = 3
        dateComponents.day = 2 + weekOffset * 7 + (dayOfWeek - 1)
        
        return calendar.date(from: dateComponents)
    }
}
