variable "github_repositories" {
  description = "List of GitHub repositories to grant access to"
  type = list(object({
    org    = string
    repo   = string
    branch = optional(string, "*")
  }))
  default = [
    {
      org    = "dimaserbenyuk"
      repo   = "devops-course"
      branch = "*"
    }
  ]
}
