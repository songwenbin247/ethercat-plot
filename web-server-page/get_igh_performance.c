#include<stdio.h>
#include<unistd.h>
#include <sys/time.h>
#include<string.h>
#include <stdlib.h>

#define PROC_FILE "/proc/ethercat/igh_ec_performance_log"

int getStrByPos(char * src, char * dst, int dst_size, int pos){
    int i = 1;
    char *p = NULL;
    if(src == NULL || strlen(src) == 0){
        goto END;
    }

    p = strtok(src, "\t");
    if (pos == 0) {
        goto END;
    }

    while((p = strtok(NULL, "\t")) && i != pos){
        i++;
    }
END:
    if(p){
        snprintf(dst, dst_size, "%s", p);
    }else{
        snprintf(dst, dst_size, "%d", 0);
    }
    return 0;
}

int main(){
	int i = 0;
	struct  timeval start_tv, end_tv, result_tv;
    FILE * proc_file = NULL, *save_file = NULL;
    char proc_buf[64], info_buf[12], buffer[64];
    char cmd[64];
    char * p;

    save_file = fopen("./save_performance", "w+");
	for (i = 0; i < 1200; i++) {
        proc_file = fopen(PROC_FILE, "r");
        if (proc_file) {
            fgets(proc_buf, sizeof(proc_buf), proc_file);
            fclose(proc_file);
        }
        getStrByPos(proc_buf, info_buf, sizeof(info_buf), 0);
    
		gettimeofday(&start_tv, NULL);
		usleep(150);
		gettimeofday(&end_tv, NULL);
        timersub(&end_tv, &start_tv, &result_tv);
        
		usleep(999850);
        snprintf(buffer, sizeof(buffer), "%s\t%s\t%ld\n", info_buf, "0", result_tv.tv_usec);
        if (save_file) {
            fputs(buffer, save_file);
        }
	}
    if (save_file) {
        fclose(save_file);
    }
    printf("Finished......\n");
    return 0;
}
