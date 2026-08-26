import RoleSummary from '../components/RoleSummary'

function WebFormPage() {
  return (
    <div className="page-shell">
      <RoleSummary
        role="Web Form"
        summary="A sample form layout for collecting user input and submissions."
        focus="Capture requests, approvals, or profile updates with a polished form experience."
      />

      <section className="content-panel">
        <h3>Request details</h3>
        <form className="sample-form">
          <label>
            Full name
            <input type="text" placeholder="Enter your name" />
          </label>
          <label>
            Email
            <input type="email" placeholder="name@example.com" />
          </label>
          <label>
            Request type
            <select>
              <option>Access request</option>
              <option>Support ticket</option>
              <option>Leave request</option>
            </select>
          </label>
          <label>
            Notes
            <textarea rows={4} placeholder="Add any context here" />
          </label>
          <button type="submit">Submit request</button>
        </form>
      </section>
    </div>
  )
}

export default WebFormPage
