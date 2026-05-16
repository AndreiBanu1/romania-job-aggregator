import { Component, inject } from '@angular/core';
import { JobsService } from '../jobs.service';

@Component({
  selector: 'app-jobs-table',
  imports: [],
  templateUrl: './jobs-table.component.html',
  styleUrl: './jobs-table.component.css',
})
export class JobsTableComponent {
  private jobsService = inject(JobsService);

  jobs = this.jobsService.jobs;
  loading = this.jobsService.loading;
}
