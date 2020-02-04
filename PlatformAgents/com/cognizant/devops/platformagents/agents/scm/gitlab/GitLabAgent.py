#-------------------------------------------------------------------------------
# Copyright 2017 Cognizant Technology Solutions
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy
# of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.
#-------------------------------------------------------------------------------
'''
Created on Feb 2, 2020
@author: 658713,302683
'''
import datetime
import json
import logging
import os
import sys
import urllib
from datetime import datetime as dateTime

from dateutil import parser

from com.cognizant.devops.platformagents.core.BaseAgent import BaseAgent


class GitLabAgent(BaseAgent):
    trackingCachePath = None

    def process(self):
        timeStampNow = lambda: dateTime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        getProjects = self.config.get("getProjects", '')
        accessToken = self.config.get("accessToken", '')
        commitsBaseEndPoint = self.config.get("commitsBaseEndPoint", '')
        startFromStr = self.config.get("startFrom", '')
        startFrom = parser.parse(startFromStr, ignoretz=True)
        getProjectsUrl = getProjects + "?access_token=" + accessToken
        enableBranches = self.config.get("enableBranches", False)
        isOptimalDataCollect = self.config.get("enableOptimizedDataRetrieval", False)
        enableBrancheDeletion = self.config.get("enableBrancheDeletion", False)
        self.setupTrackingCachePath('trackingCache')
        projects = self.getResponse(getProjectsUrl + '&per_page=100&sort=asc&page=1', 'GET', None, None, None)
        responseTemplate = self.getResponseTemplate()
        dynamicTemplate = self.config.get('dynamicTemplate', {})
        metaData = dynamicTemplate.get('metaData', {})
        branchesMetaData = metaData.get('branches', {})
        commitsMetaData = metaData.get('commits', {})
        mergeReqMetaData = metaData.get('mergeRequest', {})
        defMergeReqResTemplate = {
            "id": "mergeReqId", "state": "mergeReqState",
            "source_branch": "originBranch",
            "target_branch": "baseBranch"
        }
        mergeReqResponseTemplate = dynamicTemplate.get('mergeReqResponseTemplate', defMergeReqResTemplate)
        projectPageNum = 1
        fetchNextPage = True
        while fetchNextPage:
            if len(projects) == 0:
                break
            for project in projects:
                projectName = project.get('path_with_namespace', '')
                projectId = project.get('id', '')
                encodedProjectName = urllib.quote_plus(projectName)
                if not os.path.isfile(self.trackingCachePath + projectName + '.json'):
                    self.updateTrackingCacheFile(projectName, dict())
                projectTrackingCache = self.loadTrackingCacheFile(projectName)
                projectDefaultBranch = project.get('default_branch', None)
                commitDict = dict()
                trackingDetails = self.tracking.get(projectName, None)
                if trackingDetails is None:
                    trackingDetails = {}
                    self.tracking[projectName] = trackingDetails
                projectUpdatedAt = project.get('last_activity_at', None)
                projectUpdatedAt = parser.parse(projectUpdatedAt, ignoretz=True)
                branch_from_tracking_json = []
                for key in trackingDetails:
                    if key != "projectModificationTime":
                        branch_from_tracking_json.append(key)
                if startFrom < projectUpdatedAt:
                    trackingDetails['projectModificationTime'] = project.get('last_activity_at')
                    branches = ['master']
                    if projectDefaultBranch != 'master':
                        branches.append(projectDefaultBranch)
                    if projectName:
                        if enableBranches:
                            if isOptimalDataCollect:
                                self.retrieveMergeRequest(commitsBaseEndPoint, projectId, projectName, encodedProjectName,
                                                         projectDefaultBranch, accessToken,
                                                         trackingDetails, projectTrackingCache, startFromStr,
                                                         mergeReqMetaData,
                                                         mergeReqResponseTemplate, commitsMetaData, responseTemplate)
                                if 'commitDict' in projectTrackingCache:
                                    commitDict = projectTrackingCache['commitDict']
                            branches = []
                            allBranches = []
                            branchPage = 1
                            fetchNextBranchPage = True
                            while fetchNextBranchPage:
                                getBranchesRestUrl = commitsBaseEndPoint + encodedProjectName + '/repository/branches?access_token=' + accessToken + '&page=' + str(
                                    branchPage)
                                # print getBranchesRestUrl
                                branchDetails = self.getResponse(getBranchesRestUrl, 'GET', None, None, None)
                                for branch in branchDetails:
                                    branchName = branch['name']
                                    branchTrackingDetails = trackingDetails.get(branchName, {})
                                    branchTracking = branchTrackingDetails.get('latestCommitId', None)
                                    allBranches.append(branchName)
                                    if branchTracking is None or branchTracking != branch.get('commit', {}).get('sha',
                                                                                                                None):
                                        branches.append(branchName)
                                if len(branchDetails) == 30:
                                    branchPage = branchPage + 1
                                else:
                                    break
                            if len(branches) > 0:
                                activeBranches = [
                                    {'projectName': projectName, 'projectId': projectId, 'activeBranches': allBranches, 'gitType': 'metadata',
                                     'consumptionTime': timeStampNow()}]
                                self.publishToolsData(activeBranches, branchesMetaData)
                        if enableBrancheDeletion:
                            for key in branch_from_tracking_json:
                                if key not in allBranches:
                                    tracking = self.tracking.get(projectName, None)
                                    if tracking:
                                        lastCommitDate = trackingDetails.get(key, {}).get('latestCommitDate', None)
                                        lastCommitId = trackingDetails.get(key, {}).get('latestCommitId', None)
                                        self.updateTrackingForBranchCreateDelete(trackingDetails, projectName, key,
                                                                                 lastCommitDate, lastCommitId)
                                        tracking.pop(key)
                        self.updateTrackingJson(self.tracking)

                        branchesFound = list()
                        branchesNotFound = list()
                        if 'mergeReqBranches' in projectTrackingCache:
                            mergeReqBranches = projectTrackingCache['mergeReqBranches']
                            for branch in branches:
                                if branch in mergeReqBranches:
                                    branchesFound.append(branch)
                                else:
                                    branchesNotFound.append(branch)
                        orderedBranches = branchesFound + branchesNotFound
                        # print orderedBranches
                        injectData = dict()
                        injectData['projectName'] = projectName
                        injectData['projectId'] = projectId
                        injectData['gitType'] = 'commit'
                        injectData['fromMergeReq'] = False
                        for branch in orderedBranches:
                            hasLatestMergeReq = False
                            data = []
                            orphanCommitIdList = list()
                            if branch == projectDefaultBranch:
                                injectData['default'] = True
                            else:
                                injectData['default'] = False
                            parsedBranch = urllib.quote_plus(branch)
                            fetchNextCommitsPage = True
                            getCommitDetailsUrl = commitsBaseEndPoint + encodedProjectName + '/repository/commits?ref_name=' + parsedBranch + '&access_token=' + accessToken + '&per_page=100'
                            branchTrackingDetails = trackingDetails.get(branch, {})
                            since = branchTrackingDetails.get('latestCommitDate', None)
                            if since:
                                getCommitDetailsUrl += '&since=' + since
                            commitsPageNum = 1
                            latestCommit = None
                            while fetchNextCommitsPage:
                                try:
                                    commits = self.getResponse(getCommitDetailsUrl + '&page=' + str(commitsPageNum),
                                                               'GET', None, None, None)
                                    if latestCommit is None and len(commits) > 0:
                                        latestCommit = commits[0]
                                    for commit in commits:
                                        commitId = commit.get('id', None)
                                        if since or startFrom < parser.parse(commit["committed_date"],
                                                                             ignoretz=True):
                                            if commitId not in commitDict:
                                                injectData['consumptionTime'] = timeStampNow()
                                                data += self.parseResponse(responseTemplate, commit, injectData)
                                                commitDict[commitId] = False
                                                orphanCommitIdList.append(commitId)
                                            elif not commitDict.get(commitId, False):
                                                orphanCommitIdList.append(commitId)
                                        else:
                                            fetchNextCommitsPage = False
                                            self.updateTrackingForBranch(trackingDetails, branch, latestCommit,
                                                                         projectDefaultBranch)
                                            break
                                    if len(commits) == 0 or len(data) == 0 or len(commits) < 100:
                                        break
                                except Exception as ex:
                                    fetchNextCommitsPage = False
                                    logging.error(ex)
                                commitsPageNum = commitsPageNum + 1
                            if data or orphanCommitIdList:
                                self.updateTrackingForBranch(trackingDetails, branch, latestCommit, projectDefaultBranch,
                                                             isOptimalDataCollect, len(data), hasLatestMergeReq)
                                self.publishToolsData(data, commitsMetaData)
                                orphanBranch = {
                                    'projectName': projectName,
                                    'projectId': projectId,
                                    'branch': branch,
                                    'gitType': 'orphanBranch',
                                    'commit': orphanCommitIdList,
                                    'consumptionTime': timeStampNow()
                                }
                                self.publishToolsData([orphanBranch, ])
                            self.updateTrackingJson(self.tracking)
                            self.updateTrackingCacheFile(projectName, projectTrackingCache)
                        # tag method call
                        self.retriveTags(trackingDetails, commitsBaseEndPoint, projectId, projectName, encodedProjectName, accessToken)
            projectPageNum = projectPageNum + 1
            projects = self.getResponse(getProjectsUrl + '&per_page=100&sort=asc&page=' + str(projectPageNum), 'GET', None, None,
                                     None)

    def retriveTags(self, trackingDetails, commitsBaseEndPoint, projectId, projectName, encodedProjectName, accessToken):
        data = list()
        if 'tags' not in trackingDetails:
            tagsTrackingDict = dict()
            trackingDetails['tags'] = tagsTrackingDict
        else:
            tagsTrackingDict = trackingDetails.get('tags', {})
        tagPage = 1
        fetchNextTagPage = True
        getTagsRestUrl = commitsBaseEndPoint + encodedProjectName + '/repository/tags?private_token=' + accessToken + '&page=' + str(
            tagPage)
        tags = self.getResponse(getTagsRestUrl, 'GET', None, None, None)
        while fetchNextTagPage:
            if len(tags) == 0:
                fetchNextTagPage = False
                break
            for tag in tags:
                tagName = tag['name']
                tagSha = tag['commit']['id']
                if tagsTrackingDict.get(tagName, '') != tagSha:
                    commitList = list()
                    injectData = dict()
                    injectData['projectName'] = projectName
                    injectData['projectId'] = projectId
                    injectData['tagSha'] = tagSha
                    injectData['tagName'] = tagName
                    parsedTag = urllib.quote_plus(tagSha)
                    fetchNextCommitsPage = True
                    getCommitDetailsUrl = commitsBaseEndPoint + encodedProjectName + '/repository/commits?ref_name=' + parsedTag + '&private_token=' + accessToken + '&per_page=100'
                    commitsPageNum = 1
                    # print(getCommitDetailsUrl)
                    # print(getCommitDetailsUrl)
                    while fetchNextCommitsPage:
                        try:
                            commits = self.getResponse(getCommitDetailsUrl + '&page=' + str(commitsPageNum), 'GET',
                                                       None, None, None)
                            for commit in commits:
                                commitList.append(commit['id'])
                            if commits or len(commits) < 100:
                                fetchNextCommitsPage = False
                        except Exception as ex:
                            fetchNextCommitsPage = False
                            logging.error(ex)
                        commitsPageNum = commitsPageNum + 1
                    if len(commitList) > 0:
                        tagNode = {
                            'commits': commitList,
                            'gitType': 'tag'
                        }
                        tagNode.update(injectData)
                        tagsTrackingDict[tagName] = tagSha
                        data.append(tagNode)

            tagPage += 1
            getTagsRestUrl = commitsBaseEndPoint + encodedProjectName + '/repository/tags?private_token=' + accessToken + '&page=' + str(
                tagPage)
            tags = self.getResponse(getTagsRestUrl, 'GET', None, None, None)
        if data:
            tagMetadata = {"dataUpdateSupported": True, "uniqueKey": ["projectName", "tagName"]}
            self.publishToolsData(data, tagMetadata)
            self.updateTrackingJson(self.tracking)

    def retrieveMergeRequest(self, projectEndPoint, projectId, projectName, encodedProjectName, defaultBranch, accessToken, trackingDetails,
                            trackingCache,
                            startFrom, metaData, responseTemplate, commitMetaData, commitsResponseTemplate):
        timeStampNow = lambda: dateTime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        injectData = dict()
        mergeReqData = list()
        commitData = list()
        branchesDict = dict()
        injectData['projectName'] = projectName
        injectData['projectId'] = projectId
        injectData['fromMergeReq'] = True
        injectData['gitType'] = 'commit'
        defaultParams = 'access_token=%s' % accessToken + '&per_page=100&page={}'
        lastTrackedTimeStr = trackingDetails.get('mergeReqModificationTime', startFrom)
        lastTrackedTime = parser.parse(lastTrackedTimeStr, ignoretz=True)
        mergeReqEndPoint = projectEndPoint + encodedProjectName + '/merge_requests'
        mergeReqUrl = mergeReqEndPoint + '?state=all&sort=desc&order_by=updated_at&updated_after=%s&' % lastTrackedTimeStr
        mergeReqUrl += defaultParams
        if 'commitDict' not in trackingCache:
            trackingCache['commitDict'] = dict()
        commitDict = trackingCache['commitDict']
        trackingCache['mergeReqBranches'] = list()
        branchesList = trackingCache['mergeReqBranches']
        mergeReqPage = 1
        nextMergeReqPage = True
        isLatestMergeReqDateSet = False
        while nextMergeReqPage:
            mergeReqDetails = list()
            try:
                mergeReqDetails = self.getResponse(mergeReqUrl.format(mergeReqPage), 'GET', None, None, None)
                if mergeReqDetails and not isLatestMergeReqDateSet:
                    mergeReqLatestModifiedTime = mergeReqDetails[0].get('updated_at', None)
                    trackingDetails['mergeReqModificationTime'] = mergeReqLatestModifiedTime
                    isLatestMergeReqDateSet = True
            except Exception as err:
                logging.error(err)
            for mergeReq in mergeReqDetails:
                commitList = list()
                commitIdSet = set()
                latestCommit = dict()
                mergeReqNumber = mergeReq.get('iid', 0)
                updatedAtStr = mergeReq.get('updated_at', None)
                updatedAt = parser.parse(updatedAtStr, ignoretz=True)
                if updatedAt <= lastTrackedTime:
                    nextMergeReqPage = False
                    break
                baseMergeReqCommitUrl = mergeReqEndPoint + '/{}/commits?{}'.format(mergeReqNumber, defaultParams)
                baseBranch = mergeReq.get('target_branch', None)
                if baseBranch == defaultBranch:
                    injectData['default'] = True
                else:
                    injectData['default'] = False
                originBranch = mergeReq.get('source_branch', dict())
                originProject = mergeReq.get('source_project_id', dict())
                baseProject = mergeReq.get('target_project_id', dict())
                mergeReq['isForked'] = False if baseProject == originProject else True
                isForked = mergeReq['isForked']
                commitPage = 1
                nextMergeReqCommitPage = True
                while nextMergeReqCommitPage:
                    getMergeReqCommitUrl = baseMergeReqCommitUrl.format(commitPage)
                    commitDetails = list()
                    try:
                        commitDetails = self.getResponse(getMergeReqCommitUrl, 'GET', None, None, None)
                        if commitDetails:
                            latestCommit = commitDetails[-1]
                    except Exception as err:
                        logging.error(err)
                    for commit in commitDetails:
                        commitId = commit.get('id', '')
                        injectData['consumptionTime'] = timeStampNow()
                        commitList += self.parseResponse(commitsResponseTemplate, commit, injectData)
                        commitIdSet.add(commitId)
                        commitDict[commitId] = True
                    if len(commitDetails) < 100:
                        nextMergeReqCommitPage = False
                    else:
                        commitPage += 1
                mergedSHA = mergeReq['merge_commit_sha']
                if mergeReq.get('state', '') == 'merged' and mergedSHA:
                    commitIdSet.add(mergedSHA)
                mergeReq['commit'] = list(commitIdSet)
                branchesDict[mergeReqNumber] = originBranch
                if not isForked:
                    if originBranch not in trackingDetails:
                        trackingDetails[originBranch] = dict()
                    originTrackingDetails = trackingDetails[originBranch]
                    try:
                        latestCommitTimeStr = latestCommit.get('committed_date', None)
                        if lastTrackedTimeStr:
                            if 'latestMergeReqCommitTime' in originTrackingDetails and lastTrackedTimeStr:
                                latestCommitTime = parser.parse(latestCommitTimeStr, ignoretz=True)
                                lastCommitTimeStr = originTrackingDetails.get('latestMergeReqCommitTime', None)
                                lastCommitTime = parser.parse(lastCommitTimeStr, ignoretz=True)
                                if lastCommitTime < latestCommitTime:
                                    originTrackingDetails['latestMergeReqCommitTime'] = latestCommitTimeStr
                                    originTrackingDetails['latestMergeReqCommit'] = mergeReq.get('sha', '')
                                    originTrackingDetails['mergeReqCommitCount'] = len(commitList)
                            else:
                                originTrackingDetails['latestMergeReqCommitTime'] = latestCommitTimeStr
                                originTrackingDetails['latestMergeReqCommit'] = mergeReq.get('sha', '')
                                originTrackingDetails['mergeReqCommitCount'] = len(commitList)
                        baseBranches = set(originTrackingDetails.get('baseBranches', []))
                        baseBranches.add(baseBranch)
                        originTrackingDetails['baseBranches'] = list(baseBranches)
                        originTrackingDetails['totalMergeReqCommits'] = originTrackingDetails.get('totalMergeReqCommits',
                                                                                                 0) + len(commitList)
                    except Exception as err:
                        logging.error(err)
                if commitList:
                    mergeReqData += self.parseResponse(responseTemplate, mergeReq,
                                                      {'projectName': projectName,'projectId': projectId, 'gitType': 'mergeRequest',
                                                       'consumptionTime': timeStampNow()})
                    commitData += commitList
            if len(mergeReqDetails) < 100:
                nextMergeReqPage = False
            else:
                mergeReqPage += 1
        for branch in sorted(branchesDict.items(), key=lambda record: record[0]):
            if branch not in branchesList:
                branchesList.append(branch[1])

        if commitData:
            self.publishToolsData(mergeReqData, metaData)
            self.publishToolsData(commitData, commitMetaData)
            self.updateTrackingJson(self.tracking)
            self.updateTrackingCacheFile(projectName, trackingCache)

    def setupTrackingCachePath(self, folderName):
        self.trackingCachePath = os.path.dirname(
            sys.modules[self.__module__].__file__) + os.path.sep + folderName + os.path.sep
        if not os.path.exists(self.trackingCachePath):
            os.mkdir(self.trackingCachePath)

    def loadTrackingCacheFile(self, fileName):
        with open(self.trackingCachePath + fileName + '.json', 'r') as filePointer:
            data = json.load(filePointer)
        return data

    def updateTrackingCacheFile(self, fileName, trackingDict):
        filePath = self.trackingCachePath + fileName
        if not os.path.exists(os.path.dirname(filePath)):
            try:
                os.makedirs(os.path.dirname(filePath))
            except Exception as err:
                logging.error(err)
        with open(self.trackingCachePath + fileName + '.json', 'w') as filePointer:
            json.dump(trackingDict, filePointer)

    def updateTrackingForBranch(self, trackingDetails, branchName, latestCommit, projectDefaultBranch,
                                isOptimalDataCollect=False, totalCommit=0, hasLatestMergeReq=False):
        updatetimestamp = latestCommit["committed_date"]
        dt = parser.parse(updatetimestamp)
        fromDateTime = dt + datetime.timedelta(seconds=01)
        fromDateTime = fromDateTime.strftime(self.config.get('timeStampFormat', '%Y-%m-%dT%H:%M:%SZ'))
        if branchName in trackingDetails:
            trackingDetails[branchName]['latestCommitDate'] = fromDateTime
            trackingDetails[branchName]['latestCommitId'] = latestCommit['id']
        else:
            trackingDetails[branchName] = {'latestCommitDate': fromDateTime, 'latestCommitId': latestCommit["id"]}
        branchTrackingDetails = trackingDetails[branchName]
        if branchName == projectDefaultBranch:
            branchTrackingDetails['default'] = True
        else:
            branchTrackingDetails['default'] = False
        if isOptimalDataCollect:
            branchTrackingDetails['totalCommit'] = branchTrackingDetails.get('totalCommit', 0) + totalCommit
            if not hasLatestMergeReq:
                branchTrackingDetails['commitCount'] = branchTrackingDetails.get('commitCount', 0) + totalCommit
            elif hasLatestMergeReq:
                branchTrackingDetails['commitCount'] = totalCommit

    def updateTrackingForBranchCreateDelete(self, trackingDetails, projectName, branchName, lastCommitDate, lastCommitId):
        trackingDetails = self.tracking.get(projectName, None)
        data_branch_delete = []
        branch_delete = dict()
        branch_delete['branchName'] = branchName
        branch_delete['projectName'] = projectName
        branch_delete['event'] = "branchDeletion"
        # branch_delete['lastCommitDate'] = lastCommitDate
        # branch_delete['lastCommitId'] = lastCommitId
        data_branch_delete.append(branch_delete)
        branchMetadata = {"labels": ["METADATA"], "dataUpdateSupported": True, "uniqueKey": ["projectName", "branchName"]}
        self.publishToolsData(data_branch_delete, branchMetadata)


if __name__ == "__main__":
    GitLabAgent()
