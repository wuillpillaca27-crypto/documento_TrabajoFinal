#ifndef _METRICS_H_
#define _METRICS_H_
#define MAX_PROCS_METRIC 64
struct proc_info {
   int pid;
   int state;
   uint64 sz;
   char name[16];
};
struct sysmetrics {
   uint ticks;
   uint64 free_mem;
   int total_procs;
   int running;
   int runnable;
   int sleeping;
   int proc_count;
   struct proc_info procs[MAX_PROCS_METRIC];
};
#endif
