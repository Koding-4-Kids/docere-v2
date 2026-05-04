import { Icons } from './ClaudeChatInput'

interface Course {
  id: string
  name: string
  courseCode: string
}

interface CourseSelectorProps {
  courses: Course[]
  userName: string
  onSelect: (courseId: string) => void
}

export function CourseSelector({ courses, userName, onSelect }: CourseSelectorProps) {
  const currentHour = new Date().getHours()
  let greeting = 'Good morning'
  if (currentHour >= 12 && currentHour < 18) greeting = 'Good afternoon'
  else if (currentHour >= 18) greeting = 'Good evening'

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 animate-fade-in">
      {/* Logo */}
      <div className="mb-5">
        <Icons.Logo className="w-14 h-14 opacity-80" />
      </div>

      {/* Greeting */}
      <h1 className="text-2xl font-serif font-normal text-text-200 mb-1.5 tracking-tight">
        {greeting},{' '}
        <span className="relative inline-block">
          {userName}
          <svg
            className="absolute w-[120%] h-[10px] -bottom-0.5 -left-[10%] text-accent"
            viewBox="0 0 140 24"
            fill="none"
            preserveAspectRatio="none"
          >
            <path d="M6 16 Q 70 24, 134 14" stroke="currentColor" strokeWidth="3" strokeLinecap="round" fill="none" />
          </svg>
        </span>
      </h1>
      <p className="text-[13px] text-text-400 mb-8">What class are we working on today?</p>

      {/* Course Buttons */}
      <div className="flex flex-wrap justify-center gap-2.5 max-w-lg">
        {courses.map(course => (
          <button
            key={course.id}
            onClick={() => onSelect(course.id)}
            className="group px-5 py-3 rounded-xl border border-bg-300/70 bg-bg-100/50 hover:bg-bg-200 hover:border-accent/40 transition-all text-left"
          >
            <p className="text-[13px] font-medium text-text-200 group-hover:text-accent transition-colors">
              {course.name}
            </p>
            {course.courseCode && (
              <p className="text-[11px] text-text-500 mt-0.5">{course.courseCode}</p>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
