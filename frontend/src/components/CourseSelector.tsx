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
      <div className="mb-6">
        <Icons.Logo className="w-16 h-16" />
      </div>

      {/* Greeting */}
      <h1 className="text-3xl font-serif font-normal text-text-200 mb-2 tracking-tight">
        {greeting},{' '}
        <span className="relative inline-block">
          {userName}
          <svg
            className="absolute w-[120%] h-[12px] -bottom-1 -left-[10%] text-accent"
            viewBox="0 0 140 24"
            fill="none"
            preserveAspectRatio="none"
          >
            <path d="M6 16 Q 70 24, 134 14" stroke="currentColor" strokeWidth="3" strokeLinecap="round" fill="none" />
          </svg>
        </span>
      </h1>
      <p className="text-text-400 mb-8">What class are we working on today?</p>

      {/* Course Buttons */}
      <div className="flex flex-col gap-3 max-w-lg mx-auto w-full px-4 md:px-0 md:flex-row md:flex-wrap md:justify-center">
        {courses.map(course => (
          <button
            key={course.id}
            onClick={() => onSelect(course.id)}
            className="w-full md:w-auto px-5 py-3 rounded-xl border border-bg-300 bg-bg-0 hover:bg-bg-200 hover:border-accent/50 transition-all text-left group"
          >
            <p className="text-sm font-medium text-text-200 group-hover:text-accent transition-colors">
              {course.name}
            </p>
            <p className="text-xs text-text-400 mt-0.5">{course.courseCode}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
