import Foundation

// MARK: - Course Data Models

/// Represents a raw course entry extracted from the web page
struct RawCourseEntry: Identifiable, Codable {
    let id = UUID()
    let full: String
    let periodStart: Int
    let periodEnd: Int
    let day: Int // 0=Sunday, 1=Monday, 2=Tuesday, etc.
    
    enum CodingKeys: String, CodingKey {
        case full
        case periodStart = "period_start"
        case periodEnd = "period_end"
        case day
    }
}

/// Represents a parsed course with structured information
struct ParsedCourse: Identifiable {
    let id = UUID()
    let courseCode: String
    let courseName: String
    let teacher: String
    let location: String
    let dayOfWeek: Int // 1=Monday, 2=Tuesday, etc.
    let timeSlot: String
    let startTime: String
    let endTime: String
    let weekSpec: String
    let weekRanges: [WeekRange]
}

/// Represents a range of weeks with optional odd/even filter
struct WeekRange {
    let startWeek: Int
    let endWeek: Int
    let isOddWeeks: Bool?
    let isEvenWeeks: Bool?
}

/// Represents a calendar event for ICS export
struct CalendarEvent: Identifiable {
    let id = UUID()
    let uid: String
    let summary: String
    let location: String
    let description: String
    let startDate: Date
    let endDate: Date
    let rrule: String?
}

// MARK: - App State

/// Represents the current state of the schedule extraction process
enum ExtractionState: Equatable {
    case idle
    case loggingIn
    case navigatingToSchedule
    case waitingForData
    case extracting
    case parsed([ParsedCourse])
    case exporting
    case exported(URL)
    case error(String)
    
    static func == (lhs: ExtractionState, rhs: ExtractionState) -> Bool {
        switch (lhs, rhs) {
        case (.idle, .idle), (.loggingIn, .loggingIn), (.navigatingToSchedule, .navigatingToSchedule),
             (.waitingForData, .waitingForData), (.extracting, .extracting), (.exporting, .exporting):
            return true
        case (.parsed(let lhsCourses), .parsed(let rhsCourses)):
            return lhsCourses.count == rhsCourses.count
        case (.exported(let lhsURL), .exported(let rhsURL)):
            return lhsURL == rhsURL
        case (.error(let lhsError), .error(let rhsError)):
            return lhsError == rhsError
        default:
            return false
        }
    }
}

/// Time slot definitions for Yibin University
struct TimeSlot {
    let slotRange: String
    let startHour: Int
    let startMinute: Int
    let endHour: Int
    let endMinute: Int
    
    static let allSlots: [TimeSlot] = [
        TimeSlot(slotRange: "1-2节", startHour: 8, startMinute: 30, endHour: 10, endMinute: 5),
        TimeSlot(slotRange: "3-4节", startHour: 10, startMinute: 25, endHour: 12, endMinute: 0),
        TimeSlot(slotRange: "5-6节", startHour: 14, startMinute: 30, endHour: 16, endMinute: 5),
        TimeSlot(slotRange: "7-8节", startHour: 16, startMinute: 25, endHour: 18, endMinute: 0),
        TimeSlot(slotRange: "9-10节", startHour: 19, startMinute: 0, endHour: 20, endMinute: 35),
        TimeSlot(slotRange: "11节", startHour: 20, startMinute: 45, endHour: 21, endMinute: 30)
    ]
    
    static func time(for slotRange: String) -> TimeSlot? {
        return allSlots.first { $0.slotRange == slotRange }
    }
}
